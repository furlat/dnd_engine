"""Canonical content recipes are the map-editor's sole item identity."""

from __future__ import annotations

from pathlib import Path
from typing import get_args
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dnd.blocks.base_item import BaseItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.recipes import ContentRecipe
from dnd.core.gridmap import get_map
from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import DoorObject as DoorObject
from dnd.items.torches import WallTorch
from dnd.runtime_reset import reset_engine_runtime
from server.api_models import (
    MapEditorObjectPlaceRequest,
    MapEditorObjectRuntimeState,
    MapEditorConnectorUpsertRequest,
    MapEditorSaveMapRequest,
    MapEditorSavedMapDocument,
    MapEditorSavedObjectPlacement,
)
from server.event_server import app
from server.mapeditor_support import (
    apply_tile_patches,
    build_catalog,
    get_saved_editor_map,
    get_editor_snapshot,
    load_saved_editor_map,
    place_catalog_object,
    save_current_editor_map,
    upsert_editor_connector,
)
from server.api_models import MapEditorTilePatch


_ROOT = Path(__file__).resolve().parents[2]


def _content_entry(catalog_rows, content_id: str):
    return next(
        row
        for row in catalog_rows
        if row.recipe.ref.content_id == content_id
        and row.recipe_preset_ref is None
    )


def test_mapeditor_catalog_exactly_discovers_public_placeable_content() -> None:
    """Registry policy, not a second string map, owns editor discovery."""
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    catalog = build_catalog()

    assert catalog.content_set_digest == loaded.content_set_digest
    expected_object_refs: set[str] = set()
    expected_loot_refs: set[str] = set()
    for declaration in loaded.registry.declarations.values():
        descriptor = declaration.descriptor
        item_definition = declaration.item_definition
        if (
            descriptor.visibility is not ContentVisibility.PUBLIC
            or declaration.construction is None
            or item_definition is None
        ):
            continue
        if item_definition.persistence_policy is (
            ItemPersistencePolicy.ENVIRONMENT
        ):
            expected_object_refs.add(declaration.ref.identity_key)
        elif item_definition.persistence_policy is (
            ItemPersistencePolicy.POSSESSION
        ):
            expected_loot_refs.add(declaration.ref.identity_key)

    default_loot_rows = [
        row for row in catalog.loot if row.recipe_preset_ref is None
    ]
    assert {
        row.recipe.ref.identity_key for row in catalog.objects
    } == expected_object_refs
    assert {
        row.recipe.ref.identity_key for row in default_loot_rows
    } == expected_loot_refs

    default_recipe_digests = {
        row.recipe.recipe_digest for row in default_loot_rows
    }
    expected_preset_refs = {
        preset.ref.identity_key
        for preset in loaded.registry.recipe_presets.values()
        if (
            preset.descriptor.visibility is ContentVisibility.PUBLIC
            and (
                declaration := loaded.registry.resolve_factory(
                    preset.recipe.ref,
                )
            ).item_definition is not None
            and declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
            and preset.recipe.recipe_digest not in default_recipe_digests
        )
    }
    assert {
        row.recipe_preset_ref.identity_key
        for row in catalog.loot
        if row.recipe_preset_ref is not None
    } == expected_preset_refs

    all_rows = (*catalog.objects, *catalog.loot)
    recipe_digests = [row.recipe.recipe_digest for row in all_rows]
    assert len(recipe_digests) == len(set(recipe_digests))
    assert all(row.content_set_digest == loaded.content_set_digest for row in all_rows)

    for row in catalog.objects:
        declaration = loaded.registry.resolve_factory(row.recipe.ref)
        assert row.recipe.ref.definition_kind is (
            ContentDefinitionKind.ENVIRONMENT_OBJECT
        )
        assert declaration.descriptor.visibility is ContentVisibility.PUBLIC
        assert declaration.item_definition is not None
        assert declaration.item_definition.persistence_policy is (
            ItemPersistencePolicy.ENVIRONMENT
        )

    for row in catalog.loot:
        declaration = loaded.registry.resolve_factory(row.recipe.ref)
        assert row.recipe.ref.definition_kind is ContentDefinitionKind.ITEM
        assert declaration.descriptor.visibility is ContentVisibility.PUBLIC
        assert declaration.item_definition is not None
        assert declaration.item_definition.persistence_policy is (
            ItemPersistencePolicy.POSSESSION
        )


def test_mapeditor_place_and_save_models_have_one_exact_identity_path() -> None:
    """No public or durable item DTO retains the retired catalog string."""
    assert set(MapEditorObjectPlaceRequest.model_fields) == {
        "recipe",
        "content_set_digest",
        "position",
        "runtime_state",
    }
    assert set(MapEditorSavedObjectPlacement.model_fields) == {
        "recipe",
        "position",
        "runtime_state",
    }
    assert "catalog_id" not in MapEditorObjectPlaceRequest.model_fields
    assert "catalog_id" not in MapEditorSavedObjectPlacement.model_fields
    assert get_args(
        MapEditorSavedMapDocument.model_fields["schema_version"].annotation,
    ) == (3,)


def test_generic_placement_materializes_every_default_public_root() -> None:
    """Every default public root crosses one validated registry adapter."""
    reset_engine_runtime(grid_size=(120, 2))
    catalog = build_catalog()

    rows = (
        *catalog.objects,
        *(row for row in catalog.loot if row.recipe_preset_ref is None),
    )
    for x, row in enumerate(rows):
        placed = place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=row.recipe,
                content_set_digest=row.content_set_digest,
                position=(x, 0),
            ),
        )
        item = BaseBlock.get(UUID(placed.uuid))
        assert isinstance(item, BaseItem)
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        assert binding.recipe == row.recipe
        assert binding.content_set_digest == row.content_set_digest
        assert binding.origin is (
            ItemRuntimeOrigin.ENVIRONMENT
            if row in catalog.objects
            else ItemRuntimeOrigin.LOOT
        )


def test_placement_rejects_wrong_set_kind_policy_and_recipe_integrity() -> None:
    """Digest, ref, kind, visibility, and policy all fail before construction."""
    reset_engine_runtime(grid_size=(4, 4))
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    catalog = build_catalog()
    door = _content_entry(catalog.objects, "environment.door")

    with pytest.raises(ValueError, match="content set"):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=door.recipe,
                content_set_digest="f" * 64,
                position=(0, 0),
            ),
        )

    intrinsic = next(
        declaration
        for declaration in loaded.registry.declarations.values()
        if declaration.item_definition is not None
        and declaration.item_definition.persistence_policy
        is ItemPersistencePolicy.INTRINSIC
        and declaration.descriptor.visibility is ContentVisibility.PUBLIC
    )
    assert intrinsic.construction is not None
    intrinsic_recipe = ContentRecipe.create(
        ref=intrinsic.ref,
        parameters=intrinsic.construction.parameter_model.model_validate(
            {},
        ).model_dump(mode="json"),
    )
    with pytest.raises(ValueError, match="not placeable"):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=intrinsic_recipe,
                content_set_digest=loaded.content_set_digest,
                position=(0, 0),
            ),
        )

    tampered = door.recipe.model_dump(mode="json")
    tampered["parameters"]["is_open"] = True
    with pytest.raises(ValidationError, match="recipe_digest"):
        MapEditorObjectPlaceRequest.model_validate(
            {
                "recipe": tampered,
                "content_set_digest": loaded.content_set_digest,
                "position": [0, 0],
            },
        )


def test_schema_three_roundtrip_keeps_recipe_and_mutable_state_separate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Saved maps pin content while restoring door and light runtime state."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(4, 2))
    catalog = build_catalog()
    door = _content_entry(catalog.objects, "environment.door")
    directional_door = _content_entry(
        catalog.objects,
        "environment.directional_door",
    )
    wall_torch = _content_entry(catalog.objects, "environment.wall_torch")

    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=door.recipe,
            content_set_digest=door.content_set_digest,
            position=(0, 0),
            runtime_state=MapEditorObjectRuntimeState(is_open=True),
        ),
    )
    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=directional_door.recipe,
            content_set_digest=directional_door.content_set_digest,
            position=(1, 0),
            runtime_state=MapEditorObjectRuntimeState(is_open=True),
        ),
    )
    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=wall_torch.recipe,
            content_set_digest=wall_torch.content_set_digest,
            position=(2, 0),
            runtime_state=MapEditorObjectRuntimeState(is_lit=False),
        ),
    )

    save_current_editor_map(
        MapEditorSaveMapRequest(id="recipe_roundtrip", name="Recipe Roundtrip"),
    )
    document = get_saved_editor_map("recipe_roundtrip")
    assert document.schema_version == 3
    assert document.content_set_digest == door.content_set_digest
    assert {row.recipe.ref.content_id for row in document.object_placements} == {
        "environment.door",
        "environment.directional_door",
        "environment.wall_torch",
    }
    assert all(
        "is_open" not in row.recipe.parameters
        or row.recipe.parameters["is_open"] is False
        for row in document.object_placements
    )

    old_payload = document.model_dump(mode="json")
    old_payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        MapEditorSavedMapDocument.model_validate(old_payload)

    loaded = load_saved_editor_map("recipe_roundtrip")
    live_items = [
        BaseBlock.get(UUID(row.uuid))
        for row in loaded.floor_objects
    ]
    ordinary = next(item for item in live_items if isinstance(item, DoorObject))
    directional = next(
        item for item in live_items if isinstance(item, DirectionalDoor)
    )
    torch = next(item for item in live_items if isinstance(item, WallTorch))
    assert ordinary.is_open is True
    assert ordinary.blocks_movement is False
    assert directional.is_open is True
    assert torch.is_lit is False


def test_schema_three_save_load_preserves_progressive_elevation_tuple(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(2, 1))
    apply_tile_patches([
        MapEditorTilePatch(
            x=0,
            y=0,
            elevation_steps=-1,
            elevation_surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        ),
        MapEditorTilePatch(
            x=1,
            y=0,
            elevation_steps=0,
            elevation_surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        ),
    ])
    save_current_editor_map(
        MapEditorSaveMapRequest(id="elevated_roundtrip", name="Elevated Roundtrip"),
    )

    reset_engine_runtime(grid_size=(1, 1))
    loaded = load_saved_editor_map("elevated_roundtrip")
    first = next(tile for tile in loaded.tiles if (tile.x, tile.y) == (0, 0))
    second = next(tile for tile in loaded.tiles if (tile.x, tile.y) == (1, 0))
    assert (
        first.elevation_steps,
        first.elevation_surface_kind,
        first.slope_axis,
    ) == (-1, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)
    assert (
        second.elevation_steps,
        second.elevation_surface_kind,
        second.slope_axis,
    ) == (0, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)


def test_schema_three_save_load_preserves_typed_connector_definition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(2, 1))
    get_map().set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    definition = TraversalConnectorDefinition(
        authored_id="connector.editor.roundtrip",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="traversal.ladder",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=10,
        action_cost_type=ConnectorActionCostType.BONUS_ACTIONS,
        action_cost_amount=1,
        bidirectional=True,
        enabled=True,
        provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
    )
    mutation = upsert_editor_connector(MapEditorConnectorUpsertRequest(
        definition=definition,
    ))
    assert mutation.snapshot.connectors == [definition]
    assert mutation.connector is not None
    assert mutation.connector.authored_id == definition.authored_id
    assert mutation.connector_revision == 1
    assert mutation.connector_digest == mutation.connector.objective_digest
    original = get_map().get_connector_by_authored_id(definition.authored_id)
    assert original is not None

    metadata = save_current_editor_map(MapEditorSaveMapRequest(
        id="connector_roundtrip",
        name="Connector Roundtrip",
    ))
    document = get_saved_editor_map("connector_roundtrip")

    assert metadata.connector_count == 1
    assert document.snapshot.connectors == [definition]
    assert document.metadata.connector_digest == metadata.connector_digest

    reset_engine_runtime(grid_size=(1, 1))
    loaded = load_saved_editor_map("connector_roundtrip")
    assert loaded.connectors == [definition]
    rebuilt = get_map().get_connector_by_authored_id(definition.authored_id)
    assert rebuilt is not None
    assert rebuilt.uuid != original.uuid
    assert rebuilt.definition() == definition


def test_retired_mapeditor_identity_compatibility_code_is_absent() -> None:
    """The recipe adapter has no reverse string map or legacy loot branch."""
    support_source = (
        _ROOT / "server" / "mapeditor_support.py"
    ).read_text(encoding="utf-8")

    assert not (
        _ROOT / "dnd" / "content_system" / "legacy_item_recipes.py"
    ).exists()
    assert "_MAPEDITOR_CATALOG_ID_BY_REF" not in support_source
    assert "_catalog_id_for_floor_object" not in support_source
    assert "LEGACY_ITEM_RECIPES" not in support_source
    assert "get_legacy_item_recipe" not in support_source


def test_failed_placement_is_atomic_and_finite_charges_cannot_be_unlimited() -> None:
    """Rejected mutable state leaves no grid, block, or binding residue."""
    reset_engine_runtime(grid_size=(3, 2))
    catalog = build_catalog()
    door = _content_entry(catalog.objects, "environment.door")
    potion = _content_entry(catalog.loot, "consumable.healing_potion")
    initial_blocks = set(BaseBlock._registry)
    initial_objects = set(BaseObject._registry)
    initial_bindings = set(ITEM_RUNTIME_BINDINGS.bindings)

    with pytest.raises(ValueError, match="is_lit"):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=door.recipe,
                content_set_digest=door.content_set_digest,
                position=(0, 0),
                runtime_state=MapEditorObjectRuntimeState(is_lit=True),
            ),
        )
    with pytest.raises(ValueError, match="finite"):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=potion.recipe,
                content_set_digest=potion.content_set_digest,
                position=(1, 0),
                runtime_state=MapEditorObjectRuntimeState(charges=-1),
            ),
        )

    assert set(BaseBlock._registry) == initial_blocks
    assert set(BaseObject._registry) == initial_objects
    assert set(ITEM_RUNTIME_BINDINGS.bindings) == initial_bindings
    assert get_map()._object_positions == {}


def test_placement_requires_an_existing_tile_before_materialization() -> None:
    """An out-of-map coordinate cannot create a half-located item."""
    reset_engine_runtime(grid_size=(2, 2))
    sword = _content_entry(build_catalog().loot, "weapon.longsword")
    initial_blocks = set(BaseBlock._registry)
    initial_bindings = set(ITEM_RUNTIME_BINDINGS.bindings)

    with pytest.raises(ValueError, match="existing tile"):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=sword.recipe,
                content_set_digest=sword.content_set_digest,
                position=(999, 999),
            ),
        )

    assert set(BaseBlock._registry) == initial_blocks
    assert set(ITEM_RUNTIME_BINDINGS.bindings) == initial_bindings
    assert get_map()._object_positions == {}


def test_unknown_exact_looking_recipe_is_a_controlled_http_400() -> None:
    """An unknown registry ref is a client error, never an unhandled KeyError."""
    reset_engine_runtime(grid_size=(2, 2))
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    recipe = ContentRecipe.create(
        ref=ContentRef(
            pack_id="content.neurodragon",
            definition_kind=ContentDefinitionKind.ITEM,
            content_id="missing.mapeditor_fixture",
            content_version=1,
            definition_contract_hash="a" * 64,
        ),
        parameters={},
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/mapeditor/map/objects",
        json={
            "recipe": recipe.model_dump(mode="json"),
            "content_set_digest": loaded.content_set_digest,
            "position": [0, 0],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mapeditor_object_place_failed"
    assert get_map()._object_positions == {}


def test_schema_two_has_one_durable_object_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Object placements own durable objects; the tile snapshot cannot disagree."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(2, 2))
    door = _content_entry(build_catalog().objects, "environment.door")
    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=door.recipe,
            content_set_digest=door.content_set_digest,
            position=(0, 0),
        ),
    )
    save_current_editor_map(
        MapEditorSaveMapRequest(id="single_authority", name="Single Authority"),
    )
    document = get_saved_editor_map("single_authority")

    assert document.snapshot.floor_objects == []
    contradictory = document.model_dump(mode="json")
    contradictory["snapshot"]["floor_objects"] = [
        get_editor_snapshot().floor_objects[0].model_dump(mode="json"),
    ]
    with pytest.raises(ValidationError, match="floor_objects"):
        MapEditorSavedMapDocument.model_validate(contradictory)


def test_malformed_saved_recipe_is_rejected_before_destructive_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Complete document preflight preserves the active editor world on failure."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(2, 2))
    door = _content_entry(build_catalog().objects, "environment.door")
    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=door.recipe,
            content_set_digest=door.content_set_digest,
            position=(0, 0),
        ),
    )
    save_current_editor_map(
        MapEditorSaveMapRequest(id="bad_recipe", name="Bad Recipe"),
    )
    before = get_editor_snapshot().model_dump(mode="json")
    document = get_saved_editor_map("bad_recipe")
    payload = document.model_dump(mode="json")
    unknown = ContentRecipe.create(
        ref=ContentRef(
            pack_id="content.neurodragon",
            definition_kind=ContentDefinitionKind.ITEM,
            content_id="missing.saved_fixture",
            content_version=1,
            definition_contract_hash="b" * 64,
        ),
        parameters={},
    )
    payload["object_placements"][0]["recipe"] = unknown.model_dump(mode="json")
    (tmp_path / "bad_recipe.json").write_text(
        MapEditorSavedMapDocument.model_validate(payload).model_dump_json(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown content reference"):
        load_saved_editor_map("bad_recipe")

    assert get_editor_snapshot().model_dump(mode="json") == before


def test_temporary_saved_schema_rejects_multiple_trap_levers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The temporary editor owns at most one lever for its one trap network."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(4, 2))
    catalog = build_catalog()
    lever = _content_entry(catalog.objects, "environment.trap_lever")
    apply_tile_patches([MapEditorTilePatch(x=3, y=0, type="spike_zone")])
    for position in ((0, 0), (1, 0)):
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=lever.recipe,
                content_set_digest=lever.content_set_digest,
                position=position,
            ),
        )

    with pytest.raises(ValueError, match="one trap lever"):
        save_current_editor_map(
            MapEditorSaveMapRequest(id="two_levers", name="Two Levers"),
        )
    assert not (tmp_path / "two_levers.json").exists()


def test_temporary_saved_schema_rejects_lever_without_spike_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A saved lever cannot reload as an inert object with no linked hazard."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_engine_runtime(grid_size=(2, 2))
    lever = _content_entry(
        build_catalog().objects,
        "environment.trap_lever",
    )
    place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=lever.recipe,
            content_set_digest=lever.content_set_digest,
            position=(0, 0),
        ),
    )

    with pytest.raises(ValueError, match="requires one spike network"):
        save_current_editor_map(
            MapEditorSaveMapRequest(id="inert_lever", name="Inert Lever"),
        )
    assert not (tmp_path / "inert_lever.json").exists()
