"""Canonical identity, variants, and mechanics for NeuroDragon apparel."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items as item_exports
import dnd.items.armors as armor_definitions
from dnd.blocks.equipment import (
    BodyArmor,
    Boots,
    Gauntlets,
    Helmet,
    Shield,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.types.equipment import ArmorType, BodyPart
from dnd.items.apparel_presets import (
    NEURODRAGON_APPAREL_RECIPE_PRESETS,
)


_EXPECTED_CONTENT_IDS = (
    "armor.cloth",
    "apparel.common_clothes",
    "apparel.fine_clothes",
    "apparel.travelers_clothes",
    "apparel.costume",
    "apparel.robes",
    "apparel.cloth_shoes",
    "apparel.leather_boots",
    "apparel.sandals",
    "apparel.leather_shoes",
    "apparel.armored_boots",
    "apparel.iron_helmet",
    "apparel.wizard_hat",
    "apparel.crown",
    "apparel.spellblade_crown",
    "apparel.cloth_hood",
    "apparel.leather_hood",
    "apparel.chain_coif",
    "apparel.horned_helmet",
    "apparel.great_helm",
    "apparel.monster_helm",
    "apparel.bracers",
    "apparel.leather_gloves",
    "apparel.gauntlets",
    "apparel.monster_hands",
    "shield.wooden",
)

_EXPECTED_ARMOR = (
    (
        armor_definitions.CLOTH_ARMOR_RECIPE,
        BodyArmor,
        "Cloth Armor",
        None,
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.COMMON_CLOTHES_RECIPE,
        BodyArmor,
        "Common Clothes",
        "Common Clothes",
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.TRAVELERS_CLOTHES_RECIPE,
        BodyArmor,
        "Traveler's Clothes",
        "Traveler's Clothes",
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.FINE_CLOTHES_RECIPE,
        BodyArmor,
        "Fine Clothes",
        "Fine Clothes",
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.COSTUME_RECIPE,
        BodyArmor,
        "Costume",
        "Costume",
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.ROBES_RECIPE,
        BodyArmor,
        "Robes",
        "Robes",
        ArmorType.CLOTH,
        BodyPart.BODY,
        10,
        10,
    ),
    (
        armor_definitions.CLOTH_SHOES_RECIPE,
        Boots,
        "Cloth Shoes",
        "Cloth Shoes",
        ArmorType.CLOTH,
        BodyPart.FEET,
        0,
        10,
    ),
    (
        armor_definitions.LEATHER_BOOTS_RECIPE,
        Boots,
        "Leather Boots",
        "Leather Boots",
        ArmorType.LIGHT,
        BodyPart.FEET,
        0,
        10,
    ),
    (
        armor_definitions.SANDALS_RECIPE,
        Boots,
        "Sandals",
        "Sandals",
        ArmorType.CLOTH,
        BodyPart.FEET,
        0,
        10,
    ),
    (
        armor_definitions.LEATHER_SHOES_RECIPE,
        Boots,
        "Leather Shoes",
        "Leather Shoes",
        ArmorType.LIGHT,
        BodyPart.FEET,
        0,
        10,
    ),
    (
        armor_definitions.ARMORED_BOOTS_RECIPE,
        Boots,
        "Armored Boots",
        "Armored Boots",
        ArmorType.HEAVY,
        BodyPart.FEET,
        0,
        10,
    ),
    (
        armor_definitions.IRON_HELMET_RECIPE,
        Helmet,
        "Iron Helmet",
        None,
        ArmorType.HEAVY,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.WIZARD_HAT_RECIPE,
        Helmet,
        "Wizard's Hat",
        None,
        ArmorType.CLOTH,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.CROWN_RECIPE,
        Helmet,
        "Crown",
        None,
        ArmorType.CLOTH,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.CLOTH_HOOD_RECIPE,
        Helmet,
        "Cloth Hood",
        "Cloth Hood",
        ArmorType.CLOTH,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.LEATHER_HOOD_RECIPE,
        Helmet,
        "Leather Hood",
        "Leather Hood",
        ArmorType.LIGHT,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.CHAIN_COIF_RECIPE,
        Helmet,
        "Chain Coif",
        "Chain Coif",
        ArmorType.HEAVY,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.HORNED_HELMET_RECIPE,
        Helmet,
        "Horned Helmet",
        "Horned Helmet",
        ArmorType.HEAVY,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.GREAT_HELM_RECIPE,
        Helmet,
        "Great Helm",
        "Great Helm",
        ArmorType.HEAVY,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.MONSTER_HELM_RECIPE,
        Helmet,
        "Monster Helm",
        "Monster Helm",
        ArmorType.CLOTH,
        BodyPart.HEAD,
        0,
        10,
    ),
    (
        armor_definitions.BRACERS_RECIPE,
        Gauntlets,
        "Bracers",
        "Bracers",
        ArmorType.LIGHT,
        BodyPart.HANDS,
        0,
        10,
    ),
    (
        armor_definitions.LEATHER_GLOVES_RECIPE,
        Gauntlets,
        "Leather Gloves",
        "Leather Gloves",
        ArmorType.LIGHT,
        BodyPart.HANDS,
        0,
        10,
    ),
    (
        armor_definitions.GAUNTLETS_RECIPE,
        Gauntlets,
        "Gauntlets",
        "Gauntlets",
        ArmorType.HEAVY,
        BodyPart.HANDS,
        0,
        10,
    ),
    (
        armor_definitions.MONSTER_HANDS_RECIPE,
        Gauntlets,
        "Monster Hands",
        "Monster Hands",
        ArmorType.CLOTH,
        BodyPart.HANDS,
        0,
        10,
    ),
)

_APPAREL_VARIANTS = (
    (
        armor_definitions.COMMON_CLOTHES_RECIPE,
        "82000001",
        "Farmhand's Tunic",
        "Common Clothes",
    ),
    (
        armor_definitions.COMMON_CLOTHES_RECIPE,
        "82000009",
        "Peasant's Rags",
        "Common Clothes",
    ),
    (
        armor_definitions.TRAVELERS_CLOTHES_RECIPE,
        "84000006",
        "Thief's Garb",
        "Traveler's Clothes",
    ),
    (
        armor_definitions.COSTUME_RECIPE,
        "85000004",
        "Pit Fighter's Wrap",
        "Costume",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "8100000b",
        "Hedge Wizard's Robe",
        "Robes",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "81000008",
        "Dark Cultist Robes",
        "Robes",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "81000003",
        "Priest's Vestments",
        "Robes",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "81000004",
        "Necromancer's Robe",
        "Robes",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "81000007",
        "Acolyte's Vestments",
        "Robes",
    ),
    (
        armor_definitions.ROBES_RECIPE,
        "81000001",
        "Wizard's Robe",
        "Robes",
    ),
    (
        armor_definitions.CLOTH_SHOES_RECIPE,
        "b0000003",
        "Dark Cloth Shoes",
        "Cloth Shoes",
    ),
    (
        armor_definitions.CLOTH_SHOES_RECIPE,
        "b0000005",
        "Blue Cloth Shoes",
        "Cloth Shoes",
    ),
    (
        armor_definitions.LEATHER_BOOTS_RECIPE,
        "b0000008",
        "Dark Boots",
        "Leather Boots",
    ),
    (
        armor_definitions.LEATHER_BOOTS_RECIPE,
        "b0000009",
        "Brown Boots",
        "Leather Boots",
    ),
    (
        armor_definitions.SANDALS_RECIPE,
        "b0000002",
        "Rope Sandals",
        "Sandals",
    ),
    (
        armor_definitions.LEATHER_SHOES_RECIPE,
        "b0000007",
        "Brown Leather Shoes",
        "Leather Shoes",
    ),
)

_LEGACY_FACTORIES = frozenset(
    {
        "create_armored_boots",
        "create_bracers",
        "create_chain_coif",
        "create_cloth_armor",
        "create_cloth_hood",
        "create_cloth_shoes",
        "create_common_clothes",
        "create_costume",
        "create_crown",
        "create_fine_clothes",
        "create_gauntlets",
        "create_great_helm",
        "create_horned_helmet",
        "create_iron_helmet",
        "create_leather_boots",
        "create_leather_gloves",
        "create_leather_hood",
        "create_leather_shoes",
        "create_monster_hands",
        "create_monster_helm",
        "create_robes",
        "create_sandals",
        "create_travelers_clothes",
        "create_wizard_hat",
        "create_wooden_shield",
    },
)


def test_neurodragon_apparel_declarations_are_exact_original_possessions() -> None:
    """All twenty-six roots own stable public identity and reviewed provenance."""
    declarations = armor_definitions.NEURODRAGON_ARMOR_DECLARATIONS

    assert tuple(
        declaration.ref.content_id for declaration in declarations
    ) == _EXPECTED_CONTENT_IDS
    # Authenticated icon completeness has one owner:
    # test_183_content_icon_bindings.py::test_every_public_builtin_has_no_unresolved_icon_assets.
    for declaration in declarations:
        assert declaration.ref.pack_id == "content.neurodragon"
        assert declaration.ref.content_version == 1
        assert declaration.descriptor.ref == declaration.ref
        assert declaration.descriptor.visibility is ContentVisibility.PUBLIC
        assert declaration.descriptor.presentation.visual_variant_key
        assert declaration.descriptor.presentation.ui_group
        assert (
            declaration.provenance.primary_source_id
            == "neurodragon.original_b2b3930"
        )
        assert (
            declaration.provenance.relation
            is ContentProvenanceRelation.ORIGINAL_CONTENT
        )
        assert declaration.provenance.fidelity is ContentFidelity.COMPLETE
        assert (
            declaration.provenance.review_status
            is ContentReviewStatus.REVIEWED
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )

@pytest.mark.parametrize(
    (
        "recipe",
        "expected_type",
        "name",
        "visual_item_name",
        "armor_type",
        "body_part",
        "armor_class",
        "max_dex_bonus",
    ),
    _EXPECTED_ARMOR,
)
def test_neurodragon_apparel_default_mechanics_are_exact(
    recipe: ContentRecipe,
    expected_type: (
        type[BodyArmor] | type[Boots] | type[Helmet] | type[Gauntlets]
    ),
    name: str,
    visual_item_name: str | None,
    armor_type: ArmorType,
    body_part: BodyPart,
    armor_class: int,
    max_dex_bonus: int,
) -> None:
    """The registry hard cut preserves all default armor and visual facts."""
    owner_uuid = uuid4()
    item = materialize_item(
        recipe,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=expected_type,
    )

    assert item.source_entity_uuid == owner_uuid
    assert item.content_ref == recipe.ref
    assert item.name == name
    assert item.visual_item_name == visual_item_name
    assert item.visual_variant_id is None
    assert item.type is armor_type
    assert item.body_part is body_part
    assert item.ac.score == armor_class
    assert item.max_dex_bonus.score == max_dex_bonus


def test_neurodragon_wooden_shield_mechanics_are_exact() -> None:
    """The custom shield remains a distinct canonical +2 AC possession."""
    shield = materialize_item(
        armor_definitions.WOODEN_SHIELD_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )

    assert shield.content_ref == armor_definitions.WOODEN_SHIELD_REF
    assert shield.name == "Wooden Shield"
    assert shield.ac_bonus.score == 2


@pytest.mark.parametrize(
    ("base_recipe", "variant_id", "display_name", "visual_item_name"),
    _APPAREL_VARIANTS,
)
def test_every_authored_apparel_variant_is_a_typed_recipe(
    base_recipe: ContentRecipe,
    variant_id: str,
    display_name: str,
    visual_item_name: str,
) -> None:
    """Visual/name variants parameterize one definition instead of cloning it."""
    recipe = ContentRecipe.create(
        ref=base_recipe.ref,
        parameters={
            "visual_variant_id": variant_id,
            "display_name": display_name,
        },
    )
    item = materialize_item(
        recipe,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
    )

    assert item.content_ref == base_recipe.ref
    assert item.visual_item_name == visual_item_name
    assert item.visual_variant_id == variant_id
    assert item.name == display_name


@pytest.mark.parametrize(
    ("base_recipe", "variant_id", "expected_type", "expected_name"),
    (
        (
            armor_definitions.ROBES_RECIPE,
            "81000005",
            BodyArmor,
            "Robes",
        ),
        (
            armor_definitions.CLOTH_SHOES_RECIPE,
            "b0000004",
            Boots,
            "Cloth Shoes",
        ),
        (
            armor_definitions.IRON_HELMET_RECIPE,
            "h0000008",
            Helmet,
            "Iron Helmet",
        ),
        (
            armor_definitions.WIZARD_HAT_RECIPE,
            "h0000011",
            Helmet,
            "Wizard's Hat",
        ),
    ),
)
def test_factory_owned_visual_only_variants_are_typed_recipes(
    base_recipe: ContentRecipe,
    variant_id: str,
    expected_type: type[BodyArmor] | type[Boots] | type[Helmet],
    expected_name: str,
) -> None:
    """Class-factory variants preserve fixed labels without sideways factories."""
    recipe = ContentRecipe.create(
        ref=base_recipe.ref,
        parameters={"visual_variant_id": variant_id},
    )
    item = materialize_item(
        recipe,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=expected_type,
    )

    assert item.name == expected_name
    assert item.visual_item_name == expected_name
    assert item.visual_variant_id == variant_id


def test_neurodragon_apparel_parameter_models_are_closed() -> None:
    """Only the declared variant surface can influence materialization."""
    static_declarations = (armor_definitions.CLOTH_ARMOR_DECLARATION,)
    for declaration in static_declarations:
        assert declaration.construction is not None
        parameter_model = declaration.construction.parameter_model
        assert parameter_model.model_validate({}).model_dump() == {}
        with pytest.raises(ValidationError):
            parameter_model.model_validate({"variant": "sideways"})

    assert armor_definitions.WOODEN_SHIELD_DECLARATION.construction is not None
    wooden_shield_parameters = (
        armor_definitions
        .WOODEN_SHIELD_DECLARATION
        .construction
        .parameter_model
    )
    wooden_variant = wooden_shield_parameters.model_validate({
        "display_name": "Celtic Shield",
        "visual_variant_id": "a000000e",
    })
    assert wooden_variant.model_dump()["visual_variant_id"] == "a000000e"
    with pytest.raises(ValidationError):
        wooden_shield_parameters.model_validate({"ac_bonus": 4})

    assert armor_definitions.ROBES_DECLARATION.construction is not None
    robes_parameters = (
        armor_definitions.ROBES_DECLARATION.construction.parameter_model
    )
    with pytest.raises(ValidationError):
        robes_parameters.model_validate({"visual_variant_id": ""})
    with pytest.raises(ValidationError):
        robes_parameters.model_validate({"display_name": ""})
    assert armor_definitions.CROWN_DECLARATION.construction is not None
    crown_parameters = (
        armor_definitions.CROWN_DECLARATION.construction.parameter_model
    )
    crown_variant = crown_parameters.model_validate(
        {"display_name": "Silver Crown"},
    )
    assert crown_variant.model_dump()["display_name"] == "Silver Crown"
    with pytest.raises(ValidationError):
        crown_parameters.model_validate({"display_name": ""})
    with pytest.raises(ValidationError):
        crown_parameters.model_validate({"palette": "sideways"})


def test_apparel_presets_own_authenticated_variant_recipes() -> None:
    """Named variants are canonical presets, never scenario wardrobe repair."""
    for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS:
        preset.recipe.verify_integrity()
        assert preset.descriptor.presentation.visual_variant_key == (
            preset.recipe.parameters.get("visual_variant_id")
        )

    authored_variants = {
        (
            preset.recipe.ref.content_id,
            preset.recipe.parameters.get("visual_variant_id"),
            preset.recipe.parameters.get("display_name"),
        )
        for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS
        if preset.recipe.parameters
    }
    assert {
        (
            base_recipe.ref.content_id,
            variant_id,
            display_name,
        )
        for base_recipe, variant_id, display_name, _ in _APPAREL_VARIANTS
    } <= authored_variants


def test_neurodragon_apparel_legacy_constructor_surface_is_absent() -> None:
    """No public alias or active engine caller can bypass the materializer."""
    for name in _LEGACY_FACTORIES:
        assert not hasattr(armor_definitions, name)
        assert not hasattr(item_exports, name)

    active_references: list[str] = []
    for path in Path("dnd").rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in _LEGACY_FACTORIES
            ):
                active_references.append(f"{path}:{node.lineno}:{node.id}")
    assert active_references == []

    assert not hasattr(item_exports, "ARMORS")
    assert not hasattr(item_exports, "SHIELDS")
