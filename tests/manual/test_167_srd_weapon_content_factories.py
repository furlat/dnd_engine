"""Canonical hard-cut coverage for the SRD 5.1 mundane weapon set."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items as item_exports
import dnd.items.weapons as weapon_definitions
from dnd.blocks.equipment import (
    Weapon,
)
from dnd.content_system.icon_bindings import (
    BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.recipes import ContentRecipe
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.types.damage import DamageType
from dnd.types.equipment import WeaponProperty


_ROOT = Path(__file__).resolve().parents[2]

_LEGACY_FACTORY_NAMES = frozenset(
    {
        "create_dagger",
        "create_dart",
        "create_handaxe",
        "create_javelin",
        "create_mace",
        "create_morningstar",
        "create_quarterstaff",
        "create_sickle",
        "create_sling",
        "create_spear",
        "create_light_crossbow",
        "create_shortbow",
        "create_battleaxe",
        "create_greataxe",
        "create_greatsword",
        "create_longsword",
        "create_rapier",
        "create_scimitar",
        "create_shortsword",
        "create_trident",
        "create_warhammer",
        "create_longbow",
        "create_heavy_crossbow",
    },
)

_EXPECTED = {
    "club": (
        "Club",
        4,
        1,
        DamageType.BLUDGEONING,
        (WeaponProperty.LIGHT,),
        RangeType.REACH,
        5,
        None,
    ),
    "dagger": (
        "Dagger",
        4,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.THROWN,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "handaxe": (
        "Handaxe",
        6,
        1,
        DamageType.SLASHING,
        (WeaponProperty.LIGHT, WeaponProperty.THROWN),
        RangeType.REACH,
        5,
        None,
    ),
    "javelin": (
        "Javelin",
        6,
        1,
        DamageType.PIERCING,
        (WeaponProperty.THROWN,),
        RangeType.REACH,
        5,
        None,
    ),
    "light_hammer": (
        "Light Hammer",
        4,
        1,
        DamageType.BLUDGEONING,
        (WeaponProperty.LIGHT, WeaponProperty.THROWN),
        RangeType.REACH,
        5,
        None,
    ),
    "mace": (
        "Mace",
        6,
        1,
        DamageType.BLUDGEONING,
        (),
        RangeType.REACH,
        5,
        None,
    ),
    "quarterstaff": (
        "Quarterstaff",
        6,
        1,
        DamageType.BLUDGEONING,
        (WeaponProperty.VERSATILE,),
        RangeType.REACH,
        5,
        None,
    ),
    "sickle": (
        "Sickle",
        4,
        1,
        DamageType.SLASHING,
        (WeaponProperty.LIGHT,),
        RangeType.REACH,
        5,
        None,
    ),
    "spear": (
        "Spear",
        6,
        1,
        DamageType.PIERCING,
        (WeaponProperty.THROWN, WeaponProperty.VERSATILE),
        RangeType.REACH,
        5,
        None,
    ),
    "dart": (
        "Dart",
        4,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.FINESSE,
            WeaponProperty.RANGED,
            WeaponProperty.THROWN,
        ),
        RangeType.RANGE,
        20,
        60,
    ),
    "light_crossbow": (
        "Light Crossbow",
        8,
        1,
        DamageType.PIERCING,
        (WeaponProperty.RANGED, WeaponProperty.TWO_HANDED),
        RangeType.RANGE,
        80,
        320,
    ),
    "shortbow": (
        "Shortbow",
        6,
        1,
        DamageType.PIERCING,
        (WeaponProperty.RANGED, WeaponProperty.TWO_HANDED),
        RangeType.RANGE,
        80,
        320,
    ),
    "sling": (
        "Sling",
        4,
        1,
        DamageType.BLUDGEONING,
        (WeaponProperty.RANGED,),
        RangeType.RANGE,
        30,
        120,
    ),
    "battleaxe": (
        "Battleaxe",
        8,
        1,
        DamageType.SLASHING,
        (WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        RangeType.REACH,
        5,
        None,
    ),
    "greataxe": (
        "Greataxe",
        12,
        1,
        DamageType.SLASHING,
        (
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "greatsword": (
        "Greatsword",
        6,
        2,
        DamageType.SLASHING,
        (
            WeaponProperty.HEAVY,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.MARTIAL,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "longsword": (
        "Longsword",
        8,
        1,
        DamageType.SLASHING,
        (WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        RangeType.REACH,
        5,
        None,
    ),
    "morningstar": (
        "Morningstar",
        8,
        1,
        DamageType.PIERCING,
        (WeaponProperty.MARTIAL,),
        RangeType.REACH,
        5,
        None,
    ),
    "rapier": (
        "Rapier",
        8,
        1,
        DamageType.PIERCING,
        (WeaponProperty.FINESSE, WeaponProperty.MARTIAL),
        RangeType.REACH,
        5,
        None,
    ),
    "scimitar": (
        "Scimitar",
        6,
        1,
        DamageType.SLASHING,
        (
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "shortsword": (
        "Shortsword",
        6,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.FINESSE,
            WeaponProperty.LIGHT,
            WeaponProperty.MARTIAL,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "trident": (
        "Trident",
        6,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.THROWN,
            WeaponProperty.VERSATILE,
            WeaponProperty.MARTIAL,
        ),
        RangeType.REACH,
        5,
        None,
    ),
    "warhammer": (
        "Warhammer",
        8,
        1,
        DamageType.BLUDGEONING,
        (WeaponProperty.VERSATILE, WeaponProperty.MARTIAL),
        RangeType.REACH,
        5,
        None,
    ),
    "longbow": (
        "Longbow",
        8,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
        ),
        RangeType.RANGE,
        150,
        600,
    ),
    "heavy_crossbow": (
        "Heavy Crossbow",
        10,
        1,
        DamageType.PIERCING,
        (
            WeaponProperty.RANGED,
            WeaponProperty.TWO_HANDED,
            WeaponProperty.HEAVY,
            WeaponProperty.MARTIAL,
        ),
        RangeType.RANGE,
        100,
        400,
    ),
}
_RECIPES_BY_SOURCE_ID = MappingProxyType({
    declaration.ref.content_id.rsplit(".", maxsplit=1)[-1]: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for declaration in weapon_definitions.SRD_WEAPON_DECLARATIONS
})


def test_srd_weapon_declarations_are_exact_frozen_content() -> None:
    """All 25 playable weapons own stable refs, descriptors, and possession policy."""
    declarations = weapon_definitions.SRD_WEAPON_DECLARATIONS
    recipes = _RECIPES_BY_SOURCE_ID

    assert isinstance(recipes, MappingProxyType)
    assert tuple(recipes) == tuple(_EXPECTED)
    assert tuple(
        declaration.ref.content_id.removeprefix("weapon.")
        for declaration in declarations
    ) == tuple(_EXPECTED)
    icon_rows = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
    }
    for legacy_id, declaration in zip(_EXPECTED, declarations, strict=True):
        assert declaration.ref.pack_id == "content.srd_5_1_cc"
        assert declaration.ref.content_id == f"weapon.{legacy_id}"
        assert declaration.ref.content_version == 1
        assert declaration.descriptor.ref == declaration.ref
        assert declaration.descriptor.presentation.icon_key == (
            icon_rows[declaration.ref.identity_key].icon_key
        )
        assert (
            declaration.descriptor.presentation.visual_variant_key
            == legacy_id
        )
        assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
        assert "pp. 65-66, Weapons table:" in declaration.provenance.source_anchor
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )
        assert recipes[legacy_id].ref == declaration.ref
        assert recipes[legacy_id].parameters == {}

    with pytest.raises(TypeError):
        recipes["dagger"] = recipes["club"]  # type: ignore[index]


def test_srd_weapon_parameter_contract_allows_only_presentation_variants() -> None:
    """Named recipes may vary labels/rendering but never weapon mechanics."""
    declaration = weapon_definitions.DAGGER_DECLARATION

    assert declaration.construction is not None
    parameter_model = declaration.construction.parameter_model
    assert parameter_model.model_validate({}).model_dump(
        exclude_none=True,
    ) == {}
    variant = parameter_model.model_validate({
        "display_name": "Golden Dagger",
        "visual_variant_id": "10000003",
    })
    assert variant.model_dump()["display_name"] == "Golden Dagger"
    assert variant.model_dump()["visual_variant_id"] == "10000003"
    with pytest.raises(ValidationError):
        parameter_model.model_validate({"visual_variant_id": ""})
    with pytest.raises(ValidationError):
        parameter_model.model_validate({"damage_dice": 20})


@pytest.mark.parametrize("legacy_id", tuple(_EXPECTED))
def test_srd_weapon_recipe_materializes_exact_mechanics(legacy_id: str) -> None:
    """Every stable recipe reconstructs the previous playable weapon mechanics."""
    expected = _EXPECTED[legacy_id]
    recipe = _RECIPES_BY_SOURCE_ID[legacy_id]

    weapon = materialize_item(
        recipe,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    assert weapon.content_ref == recipe.ref
    assert weapon.name == expected[0]
    assert weapon.damage_dice == expected[1]
    assert weapon.dice_numbers == expected[2]
    assert weapon.damage_type is expected[3]
    assert tuple(weapon.properties) == expected[4]
    assert weapon.range.type is expected[5]
    assert weapon.range.normal == expected[6]
    assert weapon.range.long == expected[7]
    assert weapon.attack_bonus.normalized_score == 0


def test_removed_srd_weapon_constructor_surface_cannot_regrow() -> None:
    """No public constructor alias or legacy WEAPONS lookup survives the cut."""
    for name in _LEGACY_FACTORY_NAMES:
        assert not hasattr(weapon_definitions, name)
        assert not hasattr(item_exports, name)

    legacy_lookup = getattr(item_exports, "WEAPONS", {})
    assert not _EXPECTED.keys() & legacy_lookup.keys()

    violations: list[str] = []
    for path in (*(_ROOT / "dnd").rglob("*.py"), *(_ROOT / "tests").rglob("*.py")):
        if "to_archive" in path.parts or path == Path(__file__):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in {"dnd.items", "dnd.items.weapons"}:
                continue
            imported = _LEGACY_FACTORY_NAMES.intersection(
                alias.name for alias in node.names
            )
            if imported:
                violations.append(
                    f"{path.relative_to(_ROOT)}:{node.lineno}:"
                    f"{','.join(sorted(imported))}"
                )

    assert violations == []
