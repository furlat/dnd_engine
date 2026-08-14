"""First complete item-registry hard cut: the SRD Club."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import dnd.items.weapons as weapons_module
import dnd.items as item_exports
from dnd.blocks.equipment import Weapon
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.base_block import BaseBlock
from dnd.core.equipment_types import WeaponProperty, WeaponSlot
from dnd.core.creature_types import DamageType
from dnd.items.weapons import (
    CLUB_DECLARATION,
    CLUB_RECIPE,
    CLUB_REF,
    ClubParameters,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime
from server.api_models import MapEditorObjectPlaceRequest
from server.mapeditor_support import build_catalog, place_catalog_object


_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTION_ROOTS = (
    _ROOT / "dnd",
    _ROOT / "server",
)


def test_club_declaration_owns_exact_contract_descriptor_and_provenance() -> None:
    """Authored identity and metadata no longer come from a callable-map key."""
    assert CLUB_REF.identity_key == "content.srd_5_1_cc:item:weapon.club@1"
    assert CLUB_REF.definition_kind == ContentDefinitionKind.ITEM
    assert len(CLUB_REF.definition_contract_hash) == 64
    assert CLUB_DECLARATION.ref == CLUB_REF
    assert CLUB_DECLARATION.construction is not None
    assert CLUB_DECLARATION.construction.parameter_model is ClubParameters
    assert CLUB_DECLARATION.item_definition is not None
    assert CLUB_DECLARATION.item_definition.persistence_policy == (
        ItemPersistencePolicy.POSSESSION
    )
    assert CLUB_DECLARATION.item_definition.may_enter_character_holdings
    assert CLUB_RECIPE.ref == CLUB_REF
    assert CLUB_RECIPE.parameters == {}
    assert ContentRecipe.model_validate_json(
        CLUB_RECIPE.model_dump_json(),
    ) == CLUB_RECIPE

    descriptor = CLUB_DECLARATION.descriptor
    assert descriptor.display_name == "Club"
    assert descriptor.presentation.icon_key == "item.club"
    assert descriptor.presentation.visual_variant_key == "club"
    assert descriptor.presentation.ui_group == "weapons.simple_melee"
    assert descriptor.tags == ("melee", "simple", "srd", "weapon")

    provenance = CLUB_DECLARATION.provenance
    assert provenance.primary_source_id == "wotc.srd_5_1_cc"
    assert provenance.relation == (
        ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
    )
    assert provenance.fidelity == ContentFidelity.PARTIAL
    assert provenance.review_status == ContentReviewStatus.REVIEWED
    assert "pp. 65-66" in provenance.source_anchor

    with pytest.raises(ValidationError, match="Extra inputs"):
        ClubParameters.model_validate({"unexpected": True})


def test_club_recipe_materializes_fresh_identity_bound_equivalent_weapons() -> None:
    """One durable recipe reconstructs equivalent mechanics, never one instance."""
    runtime = ContentSystemRuntime()
    runtime.install(bootstrap_content_system())
    bindings = ItemRuntimeBindingRegistry()
    owner_uuid = uuid4()

    first = materialize_item(
        CLUB_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
        binding_registry=bindings,
        runtime=runtime,
    )
    second = materialize_item(
        CLUB_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
        binding_registry=bindings,
        runtime=runtime,
    )

    assert isinstance(first, Weapon)
    assert isinstance(second, Weapon)
    assert first is not second
    assert first.uuid != second.uuid
    assert first.attack_bonus.uuid != second.attack_bonus.uuid
    assert first.source_entity_uuid == second.source_entity_uuid == owner_uuid
    assert first.content_ref == second.content_ref == CLUB_REF
    assert first.get_semantic_key() == CLUB_REF.identity_key
    assert second.get_semantic_key() == CLUB_REF.identity_key
    assert first.name == second.name == "Club"
    assert first.dice_numbers == second.dice_numbers == 1
    assert first.damage_dice == second.damage_dice == 4
    assert first.damage_type == second.damage_type == DamageType.BLUDGEONING
    assert first.properties == second.properties == [WeaponProperty.LIGHT]
    assert first.range.normal == second.range.normal == 5
    assert first.attack_bonus.score == second.attack_bonus.score == 0
    assert runtime.materialization_count == 2
    assert bindings.require(first.uuid).recipe == CLUB_RECIPE
    assert bindings.require(first.uuid).origin == ItemRuntimeOrigin.STARTER
    assert bindings.require(second.uuid).content_set_digest == (
        runtime.require().content_set_digest
    )


def test_srd_club_users_receive_the_exact_registered_item() -> None:
    """Commoner and Acolyte retain their loadouts through the canonical recipe."""
    reset_engine_runtime(grid_size=(3, 3))
    commoner = materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID["commoner"],
        runtime_entity_uuid=uuid4(),
        display_name=(
            SRD_CREATURE_DECLARATIONS_BY_ID["commoner"].descriptor.display_name
        ),
        faction=None,
        position=(0, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.club_loadout.commoner",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    acolyte = materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID["acolyte"],
        runtime_entity_uuid=uuid4(),
        display_name=(
            SRD_CREATURE_DECLARATIONS_BY_ID["acolyte"].descriptor.display_name
        ),
        faction=None,
        position=(1, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.club_loadout.acolyte",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )

    for actor in (commoner, acolyte):
        club = actor.equipment.weapon_melee_main
        assert isinstance(club, Weapon)
        assert club.content_ref == CLUB_REF
        assert club.get_semantic_key() == CLUB_REF.identity_key
        assert club.equipped_slot == WeaponSlot.MELEE_MAIN.value


def test_mapeditor_discovers_and_places_club_by_exact_recipe() -> None:
    """The editor exposes no second external identity for the Club."""
    reset_engine_runtime(grid_size=(3, 3))
    club_entries = [
        entry
        for entry in build_catalog().loot
        if entry.recipe.ref == CLUB_REF
        and entry.recipe_preset_ref is None
    ]

    assert len(club_entries) == 1
    entry = club_entries[0]
    assert entry.display_name == "Club"
    assert entry.recipe.ref == CLUB_RECIPE.ref
    assert entry.presentation.visual_variant_key == "club"

    placed = place_catalog_object(
        MapEditorObjectPlaceRequest(
            recipe=entry.recipe,
            content_set_digest=entry.content_set_digest,
            position=(1, 1),
        ),
    )
    item = BaseBlock.get(UUID(placed.uuid))
    assert isinstance(item, Weapon)
    assert item.content_ref == CLUB_REF
    assert item.get_semantic_key() == CLUB_REF.identity_key


def test_legacy_club_factory_and_lookup_path_are_absent() -> None:
    """No alternate Club constructor remains available to production code."""
    assert not hasattr(weapons_module, "create_club")
    assert not hasattr(item_exports, "WEAPONS")

    definitions: list[tuple[str, str]] = []
    imports: list[tuple[str, str]] = []
    calls: list[tuple[str, str]] = []
    direct_club_weapon_calls: list[tuple[str, str]] = []
    for root in _PRODUCTION_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(_ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            if "create_club" not in source and not (
                "Weapon" in source and "Club" in source
            ):
                continue
            module = ast.parse(source, filename=relative)
            for node in ast.walk(module):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == "create_club":
                        definitions.append((relative, node.name))
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "create_club":
                            imports.append((relative, alias.name))
                elif isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id == "create_club"
                    ):
                        calls.append((relative, node.func.id))
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id == "Weapon"
                    ):
                        enclosing = _enclosing_function_name(module, node)
                        if enclosing == "_build_club" or any(
                            keyword.arg == "name"
                            and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value == "Club"
                            for keyword in node.keywords
                        ):
                            direct_club_weapon_calls.append(
                                (relative, enclosing),
                            )

    assert definitions == []
    assert imports == []
    assert calls == []
    assert direct_club_weapon_calls == [
        ("dnd/items/weapons.py", "_build_club"),
    ]


def _enclosing_function_name(
    module: ast.Module,
    target: ast.Call,
) -> str:
    """Return the exact top-level function that owns one constructor call."""
    for node in module.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if target in ast.walk(node):
            return node.name
    return "<module>"
