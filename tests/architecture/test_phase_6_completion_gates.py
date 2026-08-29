"""Slice 6.4 migration-specific authority and dependency gates."""

from __future__ import annotations

import ast
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT = REPOSITORY_ROOT / "dnd"
MAINTAINED_TEST_ROOTS = (
    REPOSITORY_ROOT / "tests" / "engine",
    REPOSITORY_ROOT / "tests" / "manual",
)

RETIRED_PRODUCTION_EXCLUSIONS = frozenset({
    "dnd/items/environment_content.py",
    "dnd/items/armors.py",
    "dnd/items/weapons.py",
    "dnd/items/apparel_presets.py",
    "dnd/items/authored_variant_inventory.py",
    "dnd/items/authored_variant_presets.py",
    "dnd/items/visual_variants.py",
})
RETIRED_TEST_EXCLUSIONS = frozenset({
    "tests/engine/test_dice_event_semantics.py",
    "tests/engine/test_encounter_apis.py",
    "tests/engine/test_equipment_replication_facts.py",
    "tests/manual/test_09_action_discovery_and_costs.py",
    "tests/manual/test_11_equipment_inventory_and_items.py",
    "tests/manual/test_131_advanced_item_world_legacy_contract.py",
    "tests/manual/test_legacy_reactive_reaction_coverage.py",
    "tests/manual/test_18_sessions_api_client_contract.py",
    "tests/manual/test_20_content_extension_basics.py",
    "tests/manual/test_21_spell_and_feature_extensions.py",
    "tests/manual/test_103_game_summary_store.py",
    "tests/manual/test_113_subjective_replication_routes.py",
    "tests/manual/test_120_player_replication_journal.py",
    "tests/manual/test_120_subjective_world_projection.py",
    "tests/manual/test_121_canonical_presentation_mapper.py",
    "tests/manual/test_134_stackable_usable_item_legacy_contract.py",
    "tests/manual/test_135_stealth_lighting_legacy_contract.py",
    "tests/manual/test_149_remaining_legacy_contract.py",
    "tests/manual/test_180_srd_creature_possession_bindings.py",
    "tests/manual/test_directional_environment_legacy_contract.py",
    "tests/manual/test_126_jump_legacy_contract.py",
    "tests/manual/test_126_shatter.py",
    "tests/manual/test_127_lightning_bolt.py",
    "tests/manual/test_138_mixed_damage_spell_contract.py",
    "tests/manual/test_aoe_shape_legacy_contract.py",
    "tests/manual/test_remaining_spell_legacy_contract.py",
    "tests/manual/test_remaining_zone_spell_legacy_contract.py",
    "tests/manual/test_117_player_replication_contract.py",
    "tests/manual/test_125_subjective_objective_render_parity.py",
    "tests/manual/test_178_remaining_possession_item_roots.py",
    "tests/manual/test_neurodragon_apparel_content_factories.py",
})
RETIRED_TEST_PROOF_ALLOWLIST = frozenset({
    "tests/engine/test_event_wire_visibility_contract.py",
    "tests/engine/test_direct_item_content.py",
    "tests/engine/test_runtime_identity_registries.py",
    "tests/engine/test_tile_surface_contract.py",
})
RETAINED_OWNER_ALLOWLIST = frozenset({
    "Tile.position",
    "Entity.position",
    "SpatialCondition.position",
    "Senses.position",
    "WorldObjectPlacement.position",
    "Entity.register_entity",
    "Entity.sprite_name",
    "Senses.walkable",
    "GridMap.is_walkable",
    "GridMap.is_walkable_for",
})
RETAINED_INTERNAL_ALLOWLIST = frozenset({
    "GridEntityMembershipReceipt",
    "GridMap._commit_entity_membership",
    "GridMap._publish_entity_membership",
    "GridMap._object_placements",
    "Tile._replace_entity_uuids",
    "Tile._replace_center_object_band",
    "Tile._replace_boundary_object_band",
})

# This is intentionally a small, reviewable inventory rather than a lexical
# sweep.  The scanner below only reports qualified declarations, calls, and
# receivers; ordinary coordinates and retained owner fields are not retired.
RETIRED_SEMANTIC_INVENTORY = (
    ("Phase 0-2", "_object_positions", "MUST_MIGRATE", "retired object position index"),
    ("Phase 0-2", "_objects_by_position", "MUST_MIGRATE", "retired object reverse index"),
    ("Phase 0-2", "BaseItem.tile_uuid", "MUST_MIGRATE", "BaseItem no longer owns floor placement"),
    ("Phase 0-2", "_wall_torch_position", "MUST_MIGRATE", "WallTorch placement is GridMap-owned"),
    ("Phase 0-2", "clear_object_location/clear_location", "MUST_MIGRATE", "retired placement switches"),
    ("Phase 0-2", "object_map_char", "MUST_MIGRATE", "retired object renderer field"),
    ("Phase 0-2", "direct Tile-band mutation / implicit place_object move", "MUST_MIGRATE", "GridMap-only private membership owner"),
    ("Phase 3", "Tile border_*/optical_border_*/propagation_border_* and allows_direction(s)", "MUST_MIGRATE", "retired directional Tile authorities"),
    ("Phase 3", "BaseItem directional blocker families / neutral BaseBlock directional hooks", "MUST_MIGRATE", "retired directional blocker API"),
    ("Phase 3", "get_objective_directional_structural_channels", "MUST_MIGRATE", "retired structural channel API"),
    ("Phase 3", "ItemDirectionalStructureState/directional_structure", "MUST_MIGRATE", "retired object directional state"),
    ("Phase 3", "_OBJECT_BORDER_FIELDS/_directional_block_map/recompute_tile_directional_blocking/set_tile_directional_border", "MUST_MIGRATE", "retired border recomputation owner"),
    ("Phase 3", "authored blocked_directions", "MUST_MIGRATE", "retired authored topology field"),
    ("Phase 3", "duplicate scenario topology helpers", "MUST_MIGRATE", "one topology authority"),
    ("Phase 3", "WorldTileState directional-open tuples", "MUST_MIGRATE", "directional opening is not serialized Tile state"),
    ("Phase 3", "SpatialChangeEvent directional maps", "MUST_MIGRATE", "directional maps are not authoritative event state"),
    ("Phase 3", "DoorObject", "MUST_MIGRATE", "retired duplicate door object"),
    ("Phase 3", "no-side door actions/builders/catalog identity", "MUST_MIGRATE", "retired duplicate door family"),
    ("Phase 3", "DOOR_DIRECTIONS/WALL_DIRECTIONS", "MUST_MIGRATE", "retired dead direction constants"),
    ("Phase 3", "no-arg/global barrier cache", "MUST_MIGRATE", "retired global barrier discovery"),
    ("Phase 3", "object-owned is_perceivable_by", "MUST_MIGRATE", "perception is observer-owned"),
    ("Phase 4", "Entity._entity_by_position", "MUST_MIGRATE", "retired Entity position index"),
    ("Phase 4", "GridMap._entity_positions", "MUST_MIGRATE", "retired GridMap position index"),
    ("Phase 4", "GridMap._entities_by_position", "MUST_MIGRATE", "retired GridMap reverse index"),
    ("Phase 4", "Entity.register_entity", "VALID_RETAINED", "approved identity registration entry point"),
    ("Phase 4", "GridEntityMembershipReceipt", "VALID_RETAINED_INTERNAL", "approved private commit receipt"),
    ("Phase 4", "GridEntityPositionReceipt", "MUST_MIGRATE", "retired public position receipt"),
    ("Phase 4", "Entity.get_all_entities_at_position", "MUST_MIGRATE", "retired Entity occupancy query"),
    ("Phase 4", "GridMap register_entity/unregister_entity/move_entity/stage_entity_position/publish_staged_entity_position", "MUST_MIGRATE", "retired public occupancy mutators"),
    ("Phase 5", "no separate retired public-symbol family", "VALID_RETAINED", "authored bootstrap introduced no retired authority"),
    ("Phase 6", "BaseBlock.position/set_position", "MUST_MIGRATE", "neutral BaseBlock coordinate seam"),
    ("Phase 6", "Tile.walkable/BattlefieldTileDefinition.walkable/WorldTileState.walkable/tile_walkable", "MUST_MIGRATE", "retired intrinsic walkability"),
    ("Phase 6", "Tile.sprite_name", "MUST_MIGRATE", "retired Tile renderer field"),
    ("Phase 6", "BaseItem.map_char/visual_item_name/visual_variant_id", "MUST_MIGRATE", "retired BaseItem renderer fields"),
    ("Phase 6", "BaseBlock/BaseItem.get_map_char", "MUST_MIGRATE", "retired renderer accessor"),
)

# Every MUST_MIGRATE inventory row is bound to one or more explicit AST rule
# kinds.  The inventory gate below derives its retired-name sets from this
# table, so adding a prose-only row cannot silently weaken the hard cut.
_BASE_ITEM_DIRECTIONAL_FIELDS = frozenset({
    "blocks_movement_north",
    "blocks_movement_south",
    "blocks_movement_east",
    "blocks_movement_west",
    "blocks_optics_north",
    "blocks_optics_south",
    "blocks_optics_east",
    "blocks_optics_west",
    "blocks_propagation_north",
    "blocks_propagation_south",
    "blocks_propagation_east",
    "blocks_propagation_west",
})
_BASE_ITEM_DIRECTIONAL_HELPERS = frozenset({
    "_blocks_direction",
    "_set_directional_blocking_field",
    "blocks_directional_movement",
    "blocks_directional_optics",
    "blocks_directional_propagation",
    "set_directional_blocking",
    "set_directional_blocking_bulk",
})
_TILE_DIRECTIONAL_NAMES = frozenset({
    "_intrinsic_border",
    "_derived_border",
    "set_intrinsic_border",
    "set_object_border",
    "allows_direction",
    "allows_directions",
})
_DIRECTIONAL_EVENT_NAMES = frozenset({
    "directional_position",
    "directional_directions",
    "directional_channels",
})
_RETIRED_DOOR_NAMES = frozenset({
    "OpenDoorAction",
    "CloseDoorAction",
    "door_recipe",
    "build_door",
    "DOOR_DECLARATION",
    "DOOR_REF",
    "DOOR_RECIPE",
    "DOOR_DIRECTIONS",
    "WALL_DIRECTIONS",
})

RETIRED_AST_RULES: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
    "_object_positions": (("identifier", frozenset({"_object_positions"})),),
    "_objects_by_position": (("identifier", frozenset({"_objects_by_position"})),),
    "BaseItem.tile_uuid": (("qualified_field", frozenset({"BaseItem.tile_uuid"})),),
    "_wall_torch_position": (("identifier", frozenset({"_wall_torch_position"})),),
    "clear_object_location/clear_location": (("call", frozenset({"clear_object_location", "clear_location"})),),
    "object_map_char": (("identifier", frozenset({"object_map_char"})),),
    "direct Tile-band mutation / implicit place_object move": (("owner_gate", frozenset({"Tile/GridMap private band owner"})),),
    "Tile border_*/optical_border_*/propagation_border_* and allows_direction(s)": (
        ("identifier_or_call_or_prefix", _TILE_DIRECTIONAL_NAMES | frozenset({
            "border_",
            "optical_border_",
            "propagation_border_",
            "object_movement_border_",
            "object_optical_border_",
            "object_propagation_border_",
        })),
    ),
    "BaseItem directional blocker families / neutral BaseBlock directional hooks": (
        ("identifier_or_call", _BASE_ITEM_DIRECTIONAL_FIELDS | _BASE_ITEM_DIRECTIONAL_HELPERS),
    ),
    "get_objective_directional_structural_channels": (("identifier_or_call", frozenset({"get_objective_directional_structural_channels"})),),
    "ItemDirectionalStructureState/directional_structure": (
        ("class_or_identifier_or_call", frozenset({"ItemDirectionalStructureState", "directional_structure", "get_directional_structure_state"})),
    ),
    "_OBJECT_BORDER_FIELDS/_directional_block_map/recompute_tile_directional_blocking/set_tile_directional_border": (
        ("identifier_or_call", frozenset({"_OBJECT_BORDER_FIELDS", "_directional_block_map", "get_subjective_directional_block_map", "recompute_tile_directional_blocking", "set_tile_directional_border"})),
    ),
    "authored blocked_directions": (("identifier_or_keyword", frozenset({"blocked_directions"})),),
    "duplicate scenario topology helpers": (
        ("identifier_or_call", frozenset({"_topology_cell_walkable", "_topology_side_allows", "_topology_cardinal_transition_allows", "_topology_transition_allows"})),
    ),
    "WorldTileState directional-open tuples": (("identifier_or_call", frozenset({"movement_open", "optical_open", "propagation_open"})),),
    "SpatialChangeEvent directional maps": (
        ("identifier_or_call_or_prefix", _DIRECTIONAL_EVENT_NAMES | frozenset({"directional_blocks_"})),
    ),
    "DoorObject": (("class_or_identifier_or_call", frozenset({"DoorObject"})),),
    "no-side door actions/builders/catalog identity": (
        ("class_or_identifier_or_call", _RETIRED_DOOR_NAMES),
        ("string", frozenset({"environment.door"})),
    ),
    "DOOR_DIRECTIONS/WALL_DIRECTIONS": (("identifier", frozenset({"DOOR_DIRECTIONS", "WALL_DIRECTIONS"})),),
    "no-arg/global barrier cache": (
        ("identifier", frozenset({"_barrier_positions_cache"})),
        ("zero_arg_call", frozenset({"get_barrier_positions"})),
    ),
    "object-owned is_perceivable_by": (("identifier_or_call", frozenset({"is_perceivable_by"})),),
    "Entity._entity_by_position": (("identifier", frozenset({"_entity_by_position"})),),
    "GridMap._entity_positions": (("identifier", frozenset({"_entity_positions"})),),
    "GridMap._entities_by_position": (("identifier", frozenset({"_entities_by_position"})),),
    "GridEntityPositionReceipt": (("class_or_identifier", frozenset({"GridEntityPositionReceipt"})),),
    "Entity.get_all_entities_at_position": (("call", frozenset({"get_all_entities_at_position"})),),
    "GridMap register_entity/unregister_entity/move_entity/stage_entity_position/publish_staged_entity_position": (
        ("call", frozenset({"register_entity", "unregister_entity", "move_entity", "stage_entity_position", "publish_staged_entity_position"})),
    ),
    "BaseBlock.position/set_position": (
        ("qualified_field", frozenset({"BaseBlock.position", "BaseItem.position"})),
        ("call", frozenset({"set_position"})),
    ),
    "Tile.walkable/BattlefieldTileDefinition.walkable/WorldTileState.walkable/tile_walkable": (
        ("qualified_field", frozenset({"Tile.walkable", "BattlefieldTileDefinition.walkable", "WorldTileState.walkable"})),
        ("identifier_or_keyword", frozenset({"tile_walkable"})),
    ),
    "Tile.sprite_name": (("qualified_field", frozenset({"Tile.sprite_name"})),),
    "BaseItem.map_char/visual_item_name/visual_variant_id": (
        ("qualified_field", frozenset({"BaseItem.map_char", "BaseItem.visual_item_name", "BaseItem.visual_variant_id"})),
        ("keyword", frozenset({"map_char", "visual_item_name", "visual_variant_id"})),
    ),
    "BaseBlock/BaseItem.get_map_char": (("call", frozenset({"get_map_char"})),),
}

_BASE_ITEM_FAMILY_NAMES = frozenset({
    "BaseItem",
    "WorldItem",
    "EquippableItem",
    "UsableItem",
})
_BASE_ITEM_RUNTIME_FIELDS = frozenset({
    "position",
    "tile_uuid",
    "map_char",
    "visual_item_name",
    "visual_variant_id",
})


def _rule_values(*kinds: str) -> frozenset[str]:
    return frozenset(
        value
        for specs in RETIRED_AST_RULES.values()
        for kind, values in specs
        if kind in kinds
        for value in values
    )


RETIRED_IDENTIFIER_NAMES = _rule_values(
    "identifier",
    "identifier_or_call",
    "identifier_or_call_or_prefix",
    "class_or_identifier",
    "class_or_identifier_or_call",
    "identifier_or_keyword",
)
RETIRED_IDENTIFIER_PREFIXES = frozenset(
    value
    for specs in RETIRED_AST_RULES.values()
    for kind, values in specs
    if kind == "identifier_or_call_or_prefix"
    for value in values
    if value.endswith("_")
)
RETIRED_CALL_NAMES = _rule_values(
    "call",
    "identifier_or_call",
    "identifier_or_call_or_prefix",
    "class_or_identifier_or_call",
)
RETIRED_CLASS_NAMES = _rule_values("class_or_identifier", "class_or_identifier_or_call")
RETIRED_KEYWORD_NAMES = _rule_values("keyword", "identifier_or_keyword")
RETIRED_ZERO_ARG_CALL_NAMES = _rule_values("zero_arg_call")
RETIRED_STRING_VALUES = _rule_values("string")
RETIRED_QUALIFIED_FIELD_RULES = _rule_values("qualified_field")


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPOSITORY_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _module_level_imports(path: Path) -> set[str]:
    """Collect only imports executed at module scope for the historical arrow gate."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _active_production_paths() -> list[Path]:
    return [
        path
        for path in PRODUCTION_ROOT.rglob("*.py")
        if str(path.relative_to(REPOSITORY_ROOT)) not in RETIRED_PRODUCTION_EXCLUSIONS
    ]


def test_slice_6_4_master_dependency_arrows_are_ast_enforced() -> None:
    """The exact master Section 4/16.7 forbidden arrows remain absent."""
    forbidden = {
        "dnd/core/gridmap.py": (
            "dnd.entities",
            "dnd.items",
            "dnd.spatial",
        ),
        "dnd/entities/entity.py": ("dnd.spatial",),
        "dnd/blocks/base_item.py": ("dnd.spatial",),
        "dnd/blocks/sensory.py": (
            "dnd.entities",
            "dnd.encounters",
            "dnd.content",
        ),
    }
    for relative_path, prefixes in forbidden.items():
        imported = _imports(REPOSITORY_ROOT / relative_path)
        assert not {
            (relative_path, module)
            for module in imported
            for prefix in prefixes
            if module == prefix or module.startswith(prefix + ".")
        }

    for path in (PRODUCTION_ROOT / "core" / "events").glob("*.py"):
        imported = _module_level_imports(path)
        assert not {
            (str(path.relative_to(REPOSITORY_ROOT)), module)
            for module in imported
            for prefix in (
                "dnd.core.gridmap",
                "dnd.entities",
                "dnd.blocks.sensory",
                "dnd.content",
            )
                if (
                    module == prefix or module.startswith(prefix + ".")
                )
            }

    presentation_imports = []
    forbidden_presentation_imports = []
    for path in (PRODUCTION_ROOT / "core" / "events").glob("*.py"):
        relative_path = str(path.relative_to(REPOSITORY_ROOT))
        for module in _imports(path):
            if module == "dnd.presentation":
                presentation_imports.append((relative_path, module))
            elif (
                module == "pygame"
                or module.startswith("pygame.")
                or module == "dnd.renderer"
                or module.startswith("dnd.renderer.")
                or module.startswith("dnd.presentation.")
            ):
                forbidden_presentation_imports.append((relative_path, module))
    assert presentation_imports == [
        ("dnd/core/events/action_events.py", "dnd.presentation"),
    ]
    assert forbidden_presentation_imports == []


def test_slice_6_4_gridmap_is_the_only_tile_and_reverse_placement_owner() -> None:
    """Tile replacement and the reverse placement authority have one caller."""
    replacement_names = {
        "_replace_entity_uuids",
        "_replace_center_object_band",
        "_replace_boundary_object_band",
    }
    private_band_storage_names = {
        "_entity_uuids",
        "_center_object_bands",
        "_boundary_object_bands",
    }
    callers: dict[str, set[str]] = {name: set() for name in replacement_names}
    reverse_owners: set[str] = set()
    band_storage_owners: set[str] = set()
    for path in _active_production_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module = _module_name(path)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in replacement_names
            ):
                callers[node.func.attr].add(module)
            if isinstance(node, ast.Attribute) and node.attr == "_object_placements":
                reverse_owners.add(module)
            if isinstance(node, ast.Attribute) and node.attr in private_band_storage_names:
                band_storage_owners.add(module)
    assert callers == {
        name: {"dnd.core.gridmap"}
        for name in replacement_names
    }
    assert reverse_owners == {"dnd.core.gridmap"}
    assert band_storage_owners <= {"dnd.core.base_tiles", "dnd.core.gridmap"}
    assert band_storage_owners == {"dnd.core.base_tiles", "dnd.core.gridmap"}


def test_slice_6_4_senses_projection_has_one_runtime_writer_boundary() -> None:
    """Projection writes have one reducer boundary and nav has one cache boundary."""
    perception_fields = {
        "position",
        "visible",
        "seen",
        "entities",
        "objects",
        "effective_light_levels",
        "visual_access",
        "auditory_access",
        "nonvisual_access",
    }
    navigation_fields = {
        "walkable",
        "paths",
        "path_costs",
        "safe_paths",
        "safe_path_costs",
    }
    mutator_names = {
        "clear",
        "update",
        "setdefault",
        "pop",
        "popitem",
        "add",
        "discard",
        "remove",
        "extend",
        "append",
    }
    writes: set[tuple[str, str, str, str, str]] = set()
    calls: set[tuple[str, str, str, str]] = set()

    class ScopeCalls(ast.NodeVisitor):
        """Find replacement calls and their qualified owner method."""

        def __init__(self, module: str, class_name: str, method_name: str) -> None:
            self.module = module
            self.class_name = class_name
            self.method_name = method_name

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "replace_perception",
                "replace_navigation",
            }:
                calls.add((self.module, self.class_name, self.method_name, node.func.attr))
            self.generic_visit(node)

    class FunctionMutationVisitor(ast.NodeVisitor):
        """Track simple Senses aliases and all direct/container mutations."""

        def __init__(self, module: str, class_name: str, method_name: str) -> None:
            self.module = module
            self.class_name = class_name
            self.method_name = method_name
            self.aliases = {"senses"}
            self.container_aliases: dict[str, str] = {}

        def _is_senses_expression(self, node: ast.AST) -> bool:
            if isinstance(node, ast.Name):
                return node.id in self.aliases or (
                    node.id == "self"
                    and self.class_name in {"Senses", "SpatialSensesSystem"}
                )
            if isinstance(node, ast.Attribute):
                return node.attr == "senses" or self._is_senses_expression(node.value)
            return False

        def _field_for_expression(self, node: ast.AST) -> str | None:
            if isinstance(node, ast.Name):
                return self.container_aliases.get(node.id)
            if isinstance(node, ast.Subscript):
                return self._field_for_expression(node.value)
            if isinstance(node, ast.Attribute):
                if node.attr in perception_fields | navigation_fields and self._is_senses_expression(node.value):
                    return node.attr
            return None

        def _record(self, field: str, kind: str) -> None:
            writes.add((self.module, self.class_name, self.method_name, field, kind))

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    source_field = self._field_for_expression(node.value)
                    if source_field is not None:
                        self.container_aliases[target.id] = source_field
                    elif self._is_senses_expression(node.value):
                        self.aliases.add(target.id)
                    else:
                        self.container_aliases.pop(target.id, None)
                        self.aliases.discard(target.id)
                else:
                    field = self._field_for_expression(target)
                    if field is not None:
                        self._record(field, "assignment")
            self.generic_visit(node.value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name) and node.value is not None:
                source_field = self._field_for_expression(node.value)
                if source_field is not None:
                    self.container_aliases[node.target.id] = source_field
                elif self._is_senses_expression(node.value):
                    self.aliases.add(node.target.id)
                else:
                    self.container_aliases.pop(node.target.id, None)
                    self.aliases.discard(node.target.id)
            elif not isinstance(node.target, ast.Name):
                field = self._field_for_expression(node.target)
                if field is not None:
                    self._record(field, "annotated_assignment")
            if node.value is not None:
                self.generic_visit(node.value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            if not isinstance(node.target, ast.Name):
                field = self._field_for_expression(node.target)
                if field is not None:
                    self._record(field, "augmented_assignment")
            self.generic_visit(node.value)

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr in mutator_names:
                field = self._field_for_expression(node.func.value)
                if field is not None:
                    self._record(field, f"mutator:{node.func.attr}")
            self.generic_visit(node)

    def visit_scopes(path: Path) -> None:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module = _module_name(path)
        class ScopeVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.class_name = "<module>"

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                previous = self.class_name
                self.class_name = node.name
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        FunctionMutationVisitor(module, self.class_name, child.name).visit(child)
                        ScopeCalls(module, self.class_name, child.name).visit(child)
                self.class_name = previous
                # Nested classes are irrelevant to the runtime boundary.

        ScopeVisitor().visit(tree)

    for path in _active_production_paths():
        visit_scopes(path)
    assert writes
    assert {module for module, _class, _method, _field, _kind in writes} <= {"dnd.blocks.sensory"}
    assert {
        (module, class_name, method_name)
        for module, class_name, method_name, _field, _kind in writes
        if _field in perception_fields
    } <= {
        ("dnd.blocks.sensory", "Senses", "replace_perception"),
        ("dnd.blocks.sensory", "Senses", "apply_sensory_update"),
        ("dnd.blocks.sensory", "Senses", "update_seen"),
        ("dnd.blocks.sensory", "SpatialSensesSystem", "recompute_observer"),
    }
    navigation_writes = {
        (module, class_name, method_name, field)
        for module, class_name, method_name, field, _kind in writes
        if field in navigation_fields
    }
    assert navigation_writes
    assert {
        (module, class_name, method_name)
        for module, class_name, method_name, _field in navigation_writes
    } == {
        ("dnd.blocks.sensory", "Senses", "replace_navigation"),
    }
    assert {
        (module, class_name, method_name, call_name)
        for module, class_name, method_name, call_name in calls
        if call_name == "replace_perception"
    } == {
        ("dnd.blocks.sensory", "Senses", "apply_sensory_update", "replace_perception"),
        ("dnd.blocks.sensory", "SpatialSensesSystem", "recompute_observer", "replace_perception"),
    }
    assert {
        (module, class_name, method_name, call_name)
        for module, class_name, method_name, call_name in calls
        if call_name == "replace_navigation"
    } == {
        ("dnd.entities.entity", "Entity", "materialize_navigation", "replace_navigation"),
    }


def test_slice_6_4_retired_inventory_has_explicit_retained_and_excluded_allowlists() -> None:
    """Retired Phase 0-6 names are absent from active mechanics with named exceptions."""
    assert RETAINED_OWNER_ALLOWLIST == {
        "Tile.position",
        "Entity.position",
        "SpatialCondition.position",
        "Senses.position",
        "WorldObjectPlacement.position",
        "Entity.register_entity",
        "Entity.sprite_name",
        "Senses.walkable",
        "GridMap.is_walkable",
        "GridMap.is_walkable_for",
    }
    required_inventory_rows = {
        (phase, symbol)
        for phase, symbol, _classification, _reason in RETIRED_SEMANTIC_INVENTORY
    }
    assert {
        ("Phase 0-2", "_object_positions"),
        ("Phase 0-2", "_objects_by_position"),
        ("Phase 0-2", "BaseItem.tile_uuid"),
        ("Phase 0-2", "_wall_torch_position"),
        ("Phase 0-2", "clear_object_location/clear_location"),
        ("Phase 0-2", "object_map_char"),
        ("Phase 0-2", "direct Tile-band mutation / implicit place_object move"),
        ("Phase 3", "Tile border_*/optical_border_*/propagation_border_* and allows_direction(s)"),
        ("Phase 3", "BaseItem directional blocker families / neutral BaseBlock directional hooks"),
        ("Phase 3", "get_objective_directional_structural_channels"),
        ("Phase 3", "ItemDirectionalStructureState/directional_structure"),
        ("Phase 3", "_OBJECT_BORDER_FIELDS/_directional_block_map/recompute_tile_directional_blocking/set_tile_directional_border"),
        ("Phase 3", "authored blocked_directions"),
        ("Phase 3", "duplicate scenario topology helpers"),
        ("Phase 3", "WorldTileState directional-open tuples"),
        ("Phase 3", "SpatialChangeEvent directional maps"),
        ("Phase 3", "DoorObject"),
        ("Phase 3", "no-side door actions/builders/catalog identity"),
        ("Phase 3", "DOOR_DIRECTIONS/WALL_DIRECTIONS"),
        ("Phase 3", "no-arg/global barrier cache"),
        ("Phase 3", "object-owned is_perceivable_by"),
        ("Phase 4", "Entity._entity_by_position"),
        ("Phase 4", "GridMap._entity_positions"),
        ("Phase 4", "GridMap._entities_by_position"),
        ("Phase 4", "GridEntityMembershipReceipt"),
        ("Phase 4", "GridEntityPositionReceipt"),
        ("Phase 4", "Entity.get_all_entities_at_position"),
        ("Phase 4", "GridMap register_entity/unregister_entity/move_entity/stage_entity_position/publish_staged_entity_position"),
        ("Phase 5", "no separate retired public-symbol family"),
        ("Phase 6", "BaseBlock.position/set_position"),
        ("Phase 6", "Tile.walkable/BattlefieldTileDefinition.walkable/WorldTileState.walkable/tile_walkable"),
        ("Phase 6", "Tile.sprite_name"),
        ("Phase 6", "BaseItem.map_char/visual_item_name/visual_variant_id"),
        ("Phase 6", "BaseBlock/BaseItem.get_map_char"),
    } <= required_inventory_rows
    assert {
        classification
        for _phase, _symbol, classification, _reason in RETIRED_SEMANTIC_INVENTORY
    } >= {"MUST_MIGRATE", "VALID_RETAINED", "VALID_RETAINED_INTERNAL"}
    assert RETIRED_TEST_EXCLUSIONS >= {
        "tests/engine/test_dice_event_semantics.py",
        "tests/engine/test_encounter_apis.py",
        "tests/manual/test_11_equipment_inventory_and_items.py",
        "tests/manual/test_directional_environment_legacy_contract.py",
    }

    def retired_matches(
        path: Path | None = None,
        source: str | None = None,
    ) -> list[tuple[str, int, str]]:
        if source is None:
            assert path is not None
            source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path or "<scanner-self-proof>"))
        matches: list[tuple[str, int, str]] = []

        class InventoryVisitor(ast.NodeVisitor):
            class_stack: list[str] = []

            def _record(self, symbol: str, node: ast.AST) -> None:
                matches.append((symbol, getattr(node, "lineno", 0), type(node).__name__))

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                if node.name in RETIRED_CLASS_NAMES:
                    self._record(node.name, node)
                self.class_stack.append(node.name)
                for child in node.body:
                    if isinstance(child, (ast.AnnAssign, ast.Assign)):
                        targets = [child.target] if isinstance(child, ast.AnnAssign) else child.targets
                        for target in targets:
                            item_family = (
                                node.name in _BASE_ITEM_FAMILY_NAMES
                                or node.name.endswith("Item")
                                or any(
                                    isinstance(base, ast.Name)
                                    and (
                                        base.id in _BASE_ITEM_FAMILY_NAMES
                                        or base.id.endswith("Item")
                                    )
                                    for base in node.bases
                                )
                            )
                            if (
                                isinstance(target, ast.Name)
                                and target.id in _BASE_ITEM_RUNTIME_FIELDS
                                and item_family
                            ):
                                self._record(f"BaseItem.{target.id}", target)
                            if isinstance(target, ast.Name) and target.id in {
                                "position",
                                "walkable",
                                "sprite_name",
                                "map_char",
                                "visual_item_name",
                                "visual_variant_id",
                                "tile_uuid",
                            }:
                                allowed_classes = {
                                    "position": {"BaseBlock", "BaseItem"},
                                    "walkable": {
                                        "Tile",
                                        "BattlefieldTileDefinition",
                                        "WorldTileState",
                                    },
                                    "sprite_name": {"Tile"},
                                    "map_char": {"BaseItem"},
                                    "visual_item_name": {"BaseItem"},
                                    "visual_variant_id": {"BaseItem"},
                                    "tile_uuid": {"BaseItem"},
                                }
                                if node.name in allowed_classes[target.id]:
                                    self._record(f"{node.name}.{target.id}", target)
                            if isinstance(target, ast.Name) and (
                                target.id in RETIRED_IDENTIFIER_NAMES
                                or any(
                                    target.id.startswith(prefix)
                                    for prefix in RETIRED_IDENTIFIER_PREFIXES
                                )
                            ):
                                self._record(target.id, target)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if (
                    node.name in RETIRED_CALL_NAMES
                    and self.class_stack
                    and not (
                        self.class_stack[-1] == "Entity"
                        and node.name == "register_entity"
                    )
                ):
                    self._record(node.name, node)
                if (
                    node.name in RETIRED_ZERO_ARG_CALL_NAMES
                    and self.class_stack
                    and len(node.args.args) <= 1
                    and not node.args.kwonlyargs
                ):
                    self._record(node.name, node)
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Attribute) and node.func.attr in RETIRED_CALL_NAMES:
                    retained_entity_registration = (
                        node.func.attr == "register_entity"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "Entity"
                    )
                    if not retained_entity_registration:
                        self._record(node.func.attr, node)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in RETIRED_ZERO_ARG_CALL_NAMES
                    and not node.args
                    and not node.keywords
                ):
                    self._record(node.func.attr, node)
                for keyword in node.keywords:
                    if keyword.arg in RETIRED_KEYWORD_NAMES:
                        self._record(keyword.arg, keyword)
                    if (
                        keyword.arg == "position"
                        and isinstance(node.func, ast.Name)
                        and node.func.id in _BASE_ITEM_FAMILY_NAMES
                    ):
                        self._record("BaseItem.position", keyword)
                    if keyword.arg in {"walkable", "sprite_name"} and (
                        isinstance(node.func, ast.Name)
                        and node.func.id in {
                            "Tile",
                            "BattlefieldTileDefinition",
                            "WorldTileState",
                        }
                        or isinstance(node.func, ast.Attribute)
                        and node.func.attr == "set_tile"
                    ):
                        self._record(
                            "Tile.walkable" if keyword.arg == "walkable" else "Tile.sprite_name",
                            keyword,
                        )
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute) -> None:
                if node.attr in RETIRED_IDENTIFIER_NAMES:
                    self._record(node.attr, node)
                elif any(node.attr.startswith(prefix) for prefix in RETIRED_IDENTIFIER_PREFIXES):
                    self._record(node.attr, node)
                elif node.attr == "position" and isinstance(node.value, ast.Name) and node.value.id in {
                    "block",
                    "source_block",
                }:
                    self._record(f"{node.value.id}.position", node)
                elif node.attr == "walkable" and isinstance(node.value, ast.Name) and node.value.id in {
                    "tile",
                    "world_tile",
                }:
                    self._record("Tile.walkable", node)
                elif node.attr in {"map_char", "visual_item_name", "visual_variant_id"} and isinstance(node.value, ast.Name) and node.value.id in {
                    "item",
                    "base_item",
                    "world_item",
                }:
                    self._record(f"BaseItem.{node.attr}", node)
                elif node.attr == "sprite_name" and isinstance(node.value, ast.Name) and node.value.id == "tile":
                    self._record("Tile.sprite_name", node)
                elif node.attr == "tile_uuid" and isinstance(node.value, ast.Name) and node.value.id in {
                    "item",
                    "base_item",
                    "world_item",
                }:
                    self._record("BaseItem.tile_uuid", node)
                self.generic_visit(node)

            def visit_Name(self, node: ast.Name) -> None:
                if node.id in RETIRED_IDENTIFIER_NAMES:
                    self._record(node.id, node)

            def visit_Constant(self, node: ast.Constant) -> None:
                if isinstance(node.value, str) and node.value in RETIRED_STRING_VALUES:
                    self._record(node.value, node)

        InventoryVisitor().visit(tree)
        return matches

    assert "Entity.register_entity" in RETAINED_OWNER_ALLOWLIST
    assert not any(
        symbol == "register_entity"
        for symbol, _line, _node_kind in retired_matches(
            source="Entity.register_entity(entity_uuid)",
        )
    )
    assert any(
        symbol == "register_entity"
        for symbol, _line, _node_kind in retired_matches(
            source="GridMap.register_entity(entity_uuid)",
        )
    )
    assert any(
        symbol == "register_entity"
        for symbol, _line, _node_kind in retired_matches(
            source="grid.register_entity(entity_uuid)",
        )
    )

    must_migrate_symbols = {
        symbol
        for _phase, symbol, classification, _reason in RETIRED_SEMANTIC_INVENTORY
        if classification == "MUST_MIGRATE"
    }
    assert must_migrate_symbols <= RETIRED_AST_RULES.keys()
    assert all(
        specs and all(
            kind in {
                "identifier",
                "identifier_or_call",
                "identifier_or_call_or_prefix",
                "qualified_field",
                "call",
                "class_or_identifier",
                "class_or_identifier_or_call",
                "identifier_or_keyword",
                "keyword",
                "owner_gate",
                "string",
                "zero_arg_call",
            }
            and values
            for kind, values in specs
        )
        for symbol, specs in RETIRED_AST_RULES.items()
        if symbol in must_migrate_symbols
    )

    scanned = []
    paths = _active_production_paths()
    for root in MAINTAINED_TEST_ROOTS:
        paths.extend(
            path
            for path in root.rglob("*.py")
            if str(path.relative_to(REPOSITORY_ROOT)) not in RETIRED_TEST_EXCLUSIONS
            and str(path.relative_to(REPOSITORY_ROOT)) not in RETIRED_TEST_PROOF_ALLOWLIST
        )
    for path in paths:
        matches = retired_matches(path)
        if matches:
            scanned.append((str(path.relative_to(REPOSITORY_ROOT)), matches))
    assert scanned == []
