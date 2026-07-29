"""Exact canonical identity for every production floor-object root."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.gridmap import get_map
from dnd.items.environment import (
    CloseDirectionalDoorAction,
    DirectionalDoor,
    OpenDirectionalDoorAction,
)
from dnd.items.environment_content import (
    ARCANE_DEVICE_DECLARATION,
    ARCANE_DEVICE_RECIPE,
    CAMPFIRE_DECLARATION,
    CAMPFIRE_RECIPE,
    DIRECTIONAL_DOOR_DECLARATION,
    DIRECTIONAL_DOOR_RECIPE,
    DOOR_DECLARATION,
    DOOR_RECIPE,
    STORAGE_CHEST_DECLARATION,
    TRAP_LEVER_DECLARATION,
    WALL_TORCH_DECLARATION,
    WALL_TORCH_RECIPE,
    storage_chest_recipe,
)
from dnd.items.environment_interactables import (
    ActivateDeviceAction,
    CloseDoorAction,
    CookAction,
    LootAllAction,
    OpenDoorAction,
    PullLeverAction,
    RestAction,
    DoorObject as DoorObject,
)
from dnd.items.torches import (
    ExtinguishWallTorchAction,
    IgniteWallTorchAction,
    WallTorch,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_NAME
from dnd.spells.conjuration import (
    GUARDIAN_OF_FAITH_OBJECT_RECIPE,
    HEROES_FEAST_OBJECT_RECIPE,
    HEROES_FEAST_OBJECT_DECLARATION,
    EatFromFeast,
    GuardianOfFaithObject,
    HeroesFeastObject,
)
from dnd.tiles import create_spike_zone
from server.api_models import (
    MapEditorObjectPlaceRequest,
    MapEditorObjectRuntimeState,
)
from server.mapeditor_support import (
    _saved_object_placements,
    build_catalog,
    get_editor_snapshot,
    place_catalog_object,
)


_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_IDENTITY_KEYS = frozenset({
    "content.neurodragon:environment_object:environment.arcane_machine_gun@1",
    "content.neurodragon:environment_object:environment.fireball_cannon@1",
    "content.neurodragon:environment_object:environment.arcane_device@1",
    "content.neurodragon:environment_object:environment.wall_torch@1",
    "content.neurodragon:environment_object:environment.directional_wall@1",
    "content.neurodragon:environment_object:environment.directional_door@1",
    "content.neurodragon:environment_object:environment.door@1",
    "content.neurodragon:environment_object:environment.trap_lever@1",
    "content.neurodragon:environment_object:environment.storage_chest@1",
    "content.neurodragon:environment_object:environment.campfire@1",
    "content.neurodragon:environment_object:environment.blocker.crate@1",
    "content.neurodragon:environment_object:environment.blocker.boulder@1",
    "content.neurodragon:environment_object:environment.blocker.barricade@1",
    "content.neurodragon:environment_object:environment.blocker.oil_barrel@1",
    (
        "content.srd_5_1_cc:environment_object:"
        "environment.spell_object.guardian_of_faith@1"
    ),
    (
        "content.srd_5_1_cc:environment_object:"
        "environment.spell_object.heroes_feast@1"
    ),
})
_EDITOR_OBJECT_CONTENT_IDS = (
    "environment.door",
    "environment.directional_wall",
    "environment.directional_door",
    "environment.wall_torch",
    "environment.trap_lever",
    "environment.storage_chest",
    "environment.campfire",
    "environment.arcane_device",
    "environment.arcane_machine_gun",
    "environment.fireball_cannon",
    "environment.blocker.crate",
    "environment.blocker.boulder",
    "environment.blocker.barricade",
    "environment.blocker.oil_barrel",
)
_LEGACY_FACTORY_NAMES = frozenset({
    "create_arcane_machine_gun",
    "create_fireball_cannon",
    "create_arcane_device",
    "create_wall_torch",
})
_DIRECT_CONSTRUCTOR_NAMES = frozenset({
    "DirectionalDoor",
    "DirectionalWall",
    "DoorObject",
    "TrapLever",
    "StorageChest",
    "GuardianOfFaithObject",
    "HeroesFeastObject",
})
_CONSTRUCTION_ROOTS = (
    _ROOT / "dnd" / "maps",
    _ROOT / "dnd" / "scenarios",
    _ROOT / "dnd" / "spells",
    _ROOT / "server",
)
_CANONICAL_FACTORY_FUNCTIONS = frozenset({
    "_build_guardian_of_faith_object",
    "_build_heroes_feast_object",
})


def _top_level_functions(relative_path: str) -> set[str]:
    module = ast.parse(
        (_ROOT / relative_path).read_text(encoding="utf-8"),
        filename=relative_path,
    )
    return {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _direct_production_calls() -> list[tuple[str, int, str]]:
    calls: list[tuple[str, int, str]] = []
    forbidden = _DIRECT_CONSTRUCTOR_NAMES | _LEGACY_FACTORY_NAMES
    for root in _CONSTRUCTION_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(_ROOT).as_posix()
            module = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            allowed_spans = tuple(
                (node.lineno, node.end_lineno)
                for node in module.body
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name in _CANONICAL_FACTORY_FUNCTIONS
                    and node.end_lineno is not None
                )
            )
            for node in ast.walk(module):
                if (
                    not isinstance(node, ast.Call)
                    or not isinstance(node.func, ast.Name)
                    or node.func.id not in forbidden
                ):
                    continue
                if any(
                    start <= node.lineno <= end
                    for start, end in allowed_spans
                ):
                    continue
                calls.append((relative, node.lineno, node.func.id))
    return sorted(calls)


def test_bootstrap_registers_exact_public_environment_presentations() -> None:
    """Every player-projectable root has authored presentation-only metadata."""
    loaded = bootstrap_content_system()
    declarations = loaded.registry.declarations

    assert _EXPECTED_IDENTITY_KEYS <= declarations.keys()
    for identity_key in _EXPECTED_IDENTITY_KEYS:
        declaration = declarations[identity_key]
        assert declaration.ref.definition_kind == (
            ContentDefinitionKind.ENVIRONMENT_OBJECT
        )
        assert declaration.item_definition is not None
        presentation = declaration.descriptor.presentation
        assert presentation.icon_key is not None
        assert presentation.visual_variant_key is not None
        assert presentation.ui_group is not None


def test_mapeditor_materializes_and_binds_every_environment_catalog_root() -> None:
    """All editor placements cross the registry boundary before grid placement."""
    reset_engine_runtime(grid_size=(20, 2))
    catalog = build_catalog()
    rows = {
        row.recipe.ref.content_id: row
        for row in catalog.objects
    }
    assert set(rows) == set(_EDITOR_OBJECT_CONTENT_IDS)

    for x, content_id in enumerate(_EDITOR_OBJECT_CONTENT_IDS):
        row = rows[content_id]
        placed = place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=row.recipe,
                content_set_digest=row.content_set_digest,
                position=(x, 0),
            ),
        )
        item = BaseBlock.get(UUID(placed.uuid))
        assert isinstance(item, BaseItem)
        assert item.content_ref is not None
        assert item.content_ref.identity_key in _EXPECTED_IDENTITY_KEYS
        binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
        assert binding.recipe.ref == item.content_ref
        assert binding.origin is ItemRuntimeOrigin.ENVIRONMENT


def test_mapeditor_save_identity_never_falls_back_to_runtime_name() -> None:
    """A renamed fixture saves through its authenticated ref, not display text."""
    reset_engine_runtime(grid_size=(2, 2))
    catalog = build_catalog()
    door = next(
        row
        for row in catalog.objects
        if row.recipe.ref.content_id == "environment.door"
    )
    placed = place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=door.recipe,
            content_set_digest=door.content_set_digest,
            position=(0, 0),
        ),
    )
    item = BaseBlock.get(UUID(placed.uuid))
    assert isinstance(item, BaseItem)
    item.name = "Misleading Chest Name"
    saved_floor_object = get_editor_snapshot().floor_objects[0]

    placement = _saved_object_placements([saved_floor_object])[0]
    assert placement.recipe == door.recipe


def test_spell_created_objects_are_exact_encounter_only_dependency_roots() -> None:
    """Owning spells name and materialize their exact encounter-only objects."""
    reset_engine_runtime(grid_size=(4, 4))
    loaded = bootstrap_content_system()
    cases = (
        (
            "Guardian of Faith",
            GUARDIAN_OF_FAITH_OBJECT_RECIPE,
            GuardianOfFaithObject,
        ),
        (
            "Heroes' Feast",
            HEROES_FEAST_OBJECT_RECIPE,
            HeroesFeastObject,
        ),
    )

    for spell_name, recipe, object_type in cases:
        object_declaration = loaded.registry.declarations[
            recipe.ref.identity_key
        ]
        assert object_declaration.item_definition is not None
        assert object_declaration.item_definition.persistence_policy is (
            ItemPersistencePolicy.ENCOUNTER_ONLY
        )

        spell_declaration = SPELL_CONTENT_DECLARATIONS_BY_NAME[spell_name]
        creates_object_edges = tuple(
            dependency
            for dependency in spell_declaration.dependencies
            if dependency.relation is ContentDependencyRelation.CREATES_OBJECT
        )
        assert len(creates_object_edges) == 1
        assert creates_object_edges[0].target_ref == recipe.ref

        floor_object = materialize_item(
            recipe,
            uuid4(),
            origin=ItemRuntimeOrigin.ENCOUNTER_ONLY,
            expected_type=object_type,
        )
        assert floor_object.content_ref == recipe.ref
        binding = ITEM_RUNTIME_BINDINGS.require(floor_object.uuid)
        assert binding.recipe == recipe
        assert binding.origin is ItemRuntimeOrigin.ENCOUNTER_ONLY


def test_environment_actions_bind_through_exact_provider_dependencies() -> None:
    """Static, dynamic, and encounter-linked actions retain their item root."""
    reset_engine_runtime(grid_size=(8, 2))
    expected_dependencies = (
        (
            DIRECTIONAL_DOOR_DECLARATION,
            (
                OpenDirectionalDoorAction,
                CloseDirectionalDoorAction,
            ),
        ),
        (DOOR_DECLARATION, (OpenDoorAction, CloseDoorAction)),
        (TRAP_LEVER_DECLARATION, (PullLeverAction,)),
        (STORAGE_CHEST_DECLARATION, (LootAllAction,)),
        (CAMPFIRE_DECLARATION, (RestAction, CookAction)),
        (
            WALL_TORCH_DECLARATION,
            (IgniteWallTorchAction, ExtinguishWallTorchAction),
        ),
        (ARCANE_DEVICE_DECLARATION, (ActivateDeviceAction,)),
        (HEROES_FEAST_OBJECT_DECLARATION, (EatFromFeast,)),
    )
    for declaration, action_types in expected_dependencies:
        granted_refs = tuple(
            dependency.target_ref
            for dependency in declaration.dependencies
            if dependency.relation is ContentDependencyRelation.GRANTS_ACTION
        )
        expected_refs = tuple(
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[action_type].ref
            for action_type in action_types
        )
        assert expected_refs == granted_refs

    static_cases = (
        (
            storage_chest_recipe(include_loot_all_action=True),
            (LootAllAction,),
        ),
        (
            CAMPFIRE_RECIPE,
            (RestAction, CookAction),
        ),
        (
            ARCANE_DEVICE_RECIPE,
            (ActivateDeviceAction,),
        ),
    )
    for recipe, action_types in static_cases:
        item = materialize_item(
            recipe,
            uuid4(),
            origin=ItemRuntimeOrigin.ENVIRONMENT,
        )
        assert isinstance(item, UsableItem)
        assert tuple(type(action) for action in item.use_action_templates) == (
            action_types
        )
        for action in item.use_action_templates:
            assert action.behavior_binding is not None
            assert action.behavior_binding.definition_ref == (
                ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[type(action)].ref
            )
            assert action.behavior_binding.provided_by_ref == recipe.ref
            assert action.behavior_binding.origin_root_ref == recipe.ref
            assert action.behavior_binding.runtime_owner_uuid == item.uuid

    dynamic_cases = (
        (
            DIRECTIONAL_DOOR_RECIPE,
            ItemRuntimeOrigin.ENVIRONMENT,
            DirectionalDoor,
            OpenDirectionalDoorAction,
        ),
        (
            DOOR_RECIPE,
            ItemRuntimeOrigin.ENVIRONMENT,
            DoorObject,
            OpenDoorAction,
        ),
        (
            WALL_TORCH_RECIPE,
            ItemRuntimeOrigin.ENVIRONMENT,
            WallTorch,
            IgniteWallTorchAction,
        ),
        (
            HEROES_FEAST_OBJECT_RECIPE,
            ItemRuntimeOrigin.ENCOUNTER_ONLY,
            HeroesFeastObject,
            EatFromFeast,
        ),
    )
    for recipe, origin, item_type, action_type in dynamic_cases:
        item = materialize_item(
            recipe,
            uuid4(),
            origin=origin,
            expected_type=item_type,
        )
        action = item.get_use_actions(uuid4())[0]
        assert isinstance(action, action_type)
        assert action.behavior_binding is not None
        assert action.behavior_binding.definition_ref == (
            ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[action_type].ref
        )
        assert action.behavior_binding.provided_by_ref == recipe.ref
        assert action.behavior_binding.origin_root_ref == recipe.ref
        assert action.behavior_binding.runtime_owner_uuid == item.uuid

    catalog = build_catalog()
    lever_row = next(
        row
        for row in catalog.objects
        if row.recipe.ref == TRAP_LEVER_DECLARATION.ref
    )
    trap_tiles, trap_handler = create_spike_zone({(6, 0)})
    for tile in trap_tiles:
        get_map().set_tile(6, 0, tile=tile, fire_event=False)
    linked_lever = place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=lever_row.recipe,
            content_set_digest=lever_row.content_set_digest,
            position=(7, 0),
            runtime_state=MapEditorObjectRuntimeState(
                trap_handler_uuid=str(trap_handler.uuid),
                trap_tile_uuids=tuple(str(tile.uuid) for tile in trap_tiles),
            ),
        ),
    )
    lever = BaseBlock.get(UUID(linked_lever.uuid))
    assert isinstance(lever, UsableItem)
    lever_action = lever.use_action_templates[0]
    assert lever_action.behavior_binding is not None
    assert lever_action.behavior_binding.provided_by_ref == (
        TRAP_LEVER_DECLARATION.ref
    )
    assert lever_action.behavior_binding.origin_root_ref == (
        TRAP_LEVER_DECLARATION.ref
    )
    assert lever_action.behavior_binding.runtime_owner_uuid == lever.uuid


def test_no_legacy_environment_constructor_surface_or_callsite_survives() -> None:
    """Production selects authenticated recipes, never Python constructors."""
    item_functions = set()
    for path in sorted((_ROOT / "dnd" / "items").rglob("*.py")):
        item_functions.update(
            _top_level_functions(path.relative_to(_ROOT).as_posix()),
        )
    assert _LEGACY_FACTORY_NAMES.isdisjoint(item_functions)
    assert _direct_production_calls() == []
