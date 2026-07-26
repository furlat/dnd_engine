"""Canonical identity and mechanics coverage for the SRD armor hard cut."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items
from dnd.blocks.equipment import BodyArmor, Shield
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import ArmorType
from dnd.items.armors import (
    BREASTPLATE_RECIPE,
    CHAIN_MAIL_RECIPE,
    CHAIN_SHIRT_RECIPE,
    HALF_PLATE_RECIPE,
    HIDE_ARMOR_RECIPE,
    LEATHER_ARMOR_RECIPE,
    PADDED_ARMOR_RECIPE,
    PLATE_ARMOR_RECIPE,
    RING_MAIL_RECIPE,
    SCALE_MAIL_RECIPE,
    SHIELD_RECIPE,
    SPLINT_ARMOR_RECIPE,
    SRD_ARMOR_DECLARATIONS,
    SRD_ARMOR_RECIPES_BY_LEGACY_ID,
    STUDDED_LEATHER_RECIPE,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.utils import reset_combat_state


EXPECTED_CONTENT_IDS = (
    "armor.padded",
    "armor.leather",
    "armor.studded_leather",
    "armor.hide",
    "armor.chain_shirt",
    "armor.scale_mail",
    "armor.breastplate",
    "armor.half_plate",
    "armor.ring_mail",
    "armor.chain_mail",
    "armor.splint",
    "armor.plate",
    "shield.shield",
)

EXPECTED_RECIPES = {
    "breastplate": BREASTPLATE_RECIPE,
    "chain_mail": CHAIN_MAIL_RECIPE,
    "chain_shirt": CHAIN_SHIRT_RECIPE,
    "half_plate": HALF_PLATE_RECIPE,
    "hide": HIDE_ARMOR_RECIPE,
    "leather": LEATHER_ARMOR_RECIPE,
    "padded": PADDED_ARMOR_RECIPE,
    "plate": PLATE_ARMOR_RECIPE,
    "ring_mail": RING_MAIL_RECIPE,
    "scale_mail": SCALE_MAIL_RECIPE,
    "shield": SHIELD_RECIPE,
    "splint": SPLINT_ARMOR_RECIPE,
    "studded_leather": STUDDED_LEATHER_RECIPE,
}

EXPECTED_BODY_ARMOR = (
    (
        PADDED_ARMOR_RECIPE,
        "Padded Armor",
        ArmorType.LIGHT,
        11,
        10,
        True,
        None,
    ),
    (
        LEATHER_ARMOR_RECIPE,
        "Leather Armor",
        ArmorType.LIGHT,
        11,
        10,
        False,
        None,
    ),
    (
        STUDDED_LEATHER_RECIPE,
        "Studded Leather",
        ArmorType.LIGHT,
        12,
        10,
        False,
        None,
    ),
    (
        HIDE_ARMOR_RECIPE,
        "Hide Armor",
        ArmorType.MEDIUM,
        12,
        2,
        False,
        None,
    ),
    (
        CHAIN_SHIRT_RECIPE,
        "Chain Shirt",
        ArmorType.MEDIUM,
        13,
        2,
        False,
        None,
    ),
    (
        SCALE_MAIL_RECIPE,
        "Scale Mail",
        ArmorType.MEDIUM,
        14,
        2,
        True,
        None,
    ),
    (
        BREASTPLATE_RECIPE,
        "Breastplate",
        ArmorType.MEDIUM,
        14,
        2,
        False,
        None,
    ),
    (
        HALF_PLATE_RECIPE,
        "Half Plate",
        ArmorType.MEDIUM,
        15,
        2,
        True,
        None,
    ),
    (
        RING_MAIL_RECIPE,
        "Ring Mail",
        ArmorType.HEAVY,
        14,
        0,
        True,
        None,
    ),
    (
        CHAIN_MAIL_RECIPE,
        "Chain Mail",
        ArmorType.HEAVY,
        16,
        0,
        True,
        13,
    ),
    (
        SPLINT_ARMOR_RECIPE,
        "Splint Armor",
        ArmorType.HEAVY,
        17,
        0,
        True,
        15,
    ),
    (
        PLATE_ARMOR_RECIPE,
        "Plate Armor",
        ArmorType.HEAVY,
        18,
        0,
        True,
        15,
    ),
)

LEGACY_FACTORY_NAMES = {
    "create_breastplate",
    "create_chain_mail",
    "create_chain_shirt",
    "create_half_plate",
    "create_hide_armor",
    "create_leather_armor",
    "create_padded_armor",
    "create_plate_armor",
    "create_ring_mail",
    "create_scale_mail",
    "create_shield",
    "create_splint_armor",
    "create_studded_leather",
}


def test_srd_armor_declarations_are_exact_reviewed_possessions() -> None:
    """Every official definition owns exact identity, source, and UI keys."""
    assert tuple(
        declaration.ref.content_id
        for declaration in SRD_ARMOR_DECLARATIONS
    ) == EXPECTED_CONTENT_IDS
    assert SRD_ARMOR_RECIPES_BY_LEGACY_ID == EXPECTED_RECIPES

    for declaration in SRD_ARMOR_DECLARATIONS:
        assert declaration.ref.pack_id == "content.srd_5_1_cc"
        assert declaration.ref.content_version == 1
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            == ItemPersistencePolicy.POSSESSION
        )
        assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
        assert declaration.provenance.source_anchor.startswith(
            "SRD 5.1 (CC-BY-4.0), pp. 63-64, Armor table: ",
        )
        assert declaration.provenance.fidelity == ContentFidelity.PARTIAL
        assert (
            declaration.provenance.review_status
            == ContentReviewStatus.REVIEWED
        )
        assert declaration.descriptor.presentation.icon_key
        assert declaration.descriptor.presentation.visual_variant_key
        assert declaration.descriptor.presentation.ui_group


@pytest.mark.parametrize(
    (
        "recipe",
        "name",
        "armor_type",
        "armor_class",
        "max_dex_bonus",
        "stealth_disadvantage",
        "strength_requirement",
    ),
    EXPECTED_BODY_ARMOR,
)
def test_srd_body_armor_materializes_exact_legacy_mechanics(
    recipe: ContentRecipe,
    name: str,
    armor_type: ArmorType,
    armor_class: int,
    max_dex_bonus: int,
    stealth_disadvantage: bool,
    strength_requirement: int | None,
) -> None:
    """The hard cut changes reconstruction identity, not armor mechanics."""
    owner_uuid = uuid4()
    armor = materialize_item(
        recipe,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    assert armor.source_entity_uuid == owner_uuid
    assert armor.content_ref == recipe.ref
    assert armor.name == name
    assert armor.type == armor_type
    assert armor.ac.score == armor_class
    assert armor.max_dex_bonus.score == max_dex_bonus
    assert armor.stealth_disadvantage is stealth_disadvantage
    assert armor.strength_requirement == strength_requirement


def test_srd_shield_materializes_exact_legacy_mechanics() -> None:
    """The canonical shield remains an off-hand +2 AC possession."""
    owner_uuid = uuid4()
    shield = materialize_item(
        SHIELD_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )

    assert shield.source_entity_uuid == owner_uuid
    assert shield.content_ref == SHIELD_RECIPE.ref
    assert shield.name == "Shield"
    assert shield.ac_bonus.score == 2


def test_srd_armor_reconstruction_is_fresh_and_parameter_closed() -> None:
    """Recipes preserve semantic identity without sharing runtime state."""
    first = materialize_item(
        LEATHER_ARMOR_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    second = materialize_item(
        LEATHER_ARMOR_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    assert first.uuid != second.uuid
    assert first.ac.uuid != second.ac.uuid
    assert first.max_dex_bonus.uuid != second.max_dex_bonus.uuid
    assert first.content_ref == second.content_ref == LEATHER_ARMOR_RECIPE.ref

    malformed = ContentRecipe.create(
        ref=LEATHER_ARMOR_RECIPE.ref,
        parameters={"unsupported": True},
    )
    with pytest.raises(ValidationError):
        materialize_item(
            malformed,
            uuid4(),
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=BodyArmor,
        )


def test_srd_creature_loadouts_use_canonical_armor_and_shield_recipes() -> None:
    """Representative NPC loadouts reconstruct through the frozen registry."""
    reset_combat_state()
    guard = materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID["guard"],
        runtime_entity_uuid=uuid4(),
        display_name=(
            SRD_CREATURE_DECLARATIONS_BY_ID["guard"].descriptor.display_name
        ),
        faction=None,
        position=(0, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.srd_armor.guard",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    knight = materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID["knight"],
        runtime_entity_uuid=uuid4(),
        display_name=(
            SRD_CREATURE_DECLARATIONS_BY_ID["knight"].descriptor.display_name
        ),
        faction=None,
        position=(1, 0),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.srd_armor.knight",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )

    assert guard.equipment.body_armor is not None
    assert guard.equipment.body_armor.content_ref == CHAIN_SHIRT_RECIPE.ref
    assert isinstance(guard.equipment.weapon_melee_off, Shield)
    assert guard.equipment.weapon_melee_off.content_ref == SHIELD_RECIPE.ref
    assert knight.equipment.body_armor is not None
    assert knight.equipment.body_armor.content_ref == PLATE_ARMOR_RECIPE.ref


def test_srd_armor_has_no_public_legacy_factory_or_lookup_path() -> None:
    """Active production modules cannot construct migrated armor sideways."""
    armor_module = Path("dnd/items/armors.py")
    tree = ast.parse(armor_module.read_text(encoding="utf-8"))
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert function_names.isdisjoint(LEGACY_FACTORY_NAMES)

    active_references: list[str] = []
    for path in Path("dnd").rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in LEGACY_FACTORY_NAMES
            ):
                active_references.append(f"{path}:{node.lineno}:{node.id}")
    assert active_references == []

    assert not hasattr(dnd.items, "ARMORS")
    assert not hasattr(dnd.items, "SHIELDS")
