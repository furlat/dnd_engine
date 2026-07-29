"""Curated sub-items are named recipes, not duplicate mechanics factories."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.recipe_presets import (
    CONTENT_RECIPE_PRESETS_EXPORT,
    ContentRecipePreset,
    scan_module_content_recipe_presets,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registry import ContentRegistryBuilder
from dnd.items.armors import ROBES_DECLARATION, ROBES_REF
from dnd.items.apparel_presets import (
    APPAREL_RECIPE_PRESETS_BY_VISUAL_VARIANT_ID,
    NEURODRAGON_APPAREL_RECIPE_PRESETS,
)
from server.content_catalog import build_public_content_catalog


def _red_robe_preset(
    *,
    pack_id: str = "content.neurodragon",
    preset_id: str = "apparel.red_mage_robe",
    recipe: ContentRecipe | None = None,
    visibility: ContentVisibility = ContentVisibility.PUBLIC,
) -> ContentRecipePreset:
    return ContentRecipePreset.create(
        pack_id=pack_id,
        preset_id=preset_id,
        preset_version=1,
        recipe=recipe or ContentRecipe.create(
            ref=ROBES_REF,
            parameters={
                "visual_variant_id": "81000005",
                "display_name": "Red Mage Robe",
            },
        ),
        descriptor=ContentDescriptorSpec(
            display_name="Red Mage Robe",
            description="A red battle-sorcerer robe variant.",
            tags=("apparel", "red", "sorcerer"),
            visibility=visibility,
            presentation=ContentPresentation(
                visual_variant_key="81000005",
                ui_group="apparel.body",
            ),
            ordering=ContentOrdering(
                sort_group="apparel.body",
                sort_order=105,
            ),
        ),
        provenance=ROBES_DECLARATION.provenance,
    )


def _builder() -> ContentRegistryBuilder:
    loaded = bootstrap_content_system()
    builder = ContentRegistryBuilder()
    builder.add_source(
        loaded.registry.sources[
            ROBES_DECLARATION.provenance.primary_source_id
        ],
    )
    builder.add_declaration(ROBES_DECLARATION)
    return builder


def test_preset_identity_is_separate_from_visual_key_and_authenticates_recipe() -> None:
    preset = _red_robe_preset()

    assert preset.ref.identity_key == (
        "content.neurodragon:recipe_preset:apparel.red_mage_robe@1"
    )
    assert preset.recipe.ref == ROBES_REF
    assert preset.recipe.parameters["visual_variant_id"] == "81000005"
    assert preset.descriptor.presentation.visual_variant_key == "81000005"
    assert preset.ref.preset_id != "81000005"

    tampered = preset.model_dump(mode="json")
    tampered["descriptor"]["display_name"] = "Blue Mage Robe"
    with pytest.raises(ValidationError, match="preset_contract_hash"):
        ContentRecipePreset.model_validate(tampered)


def test_registry_resolves_one_preset_and_validates_typed_parameters() -> None:
    preset = _red_robe_preset()
    builder = _builder()
    builder.add_recipe_preset(preset)

    registry = builder.freeze(
        pack_dependencies={"content.neurodragon": frozenset()},
    )

    assert registry.resolve_recipe_preset(preset.ref) == preset
    assert registry.recipe_presets[preset.ref.identity_key] == preset


def test_registry_rejects_unknown_parameters_and_recipe_aliases() -> None:
    invalid_recipe = ContentRecipe.create(
        ref=ROBES_REF,
        parameters={"unknown_visual_switch": True},
    )
    builder = _builder()
    builder.add_recipe_preset(_red_robe_preset(recipe=invalid_recipe))
    with pytest.raises(ValidationError, match="unknown_visual_switch"):
        builder.freeze(
            pack_dependencies={"content.neurodragon": frozenset()},
        )

    first = _red_robe_preset()
    alias = _red_robe_preset(
        preset_id="apparel.red_mage_robe_alias",
        recipe=first.recipe,
    )
    builder = _builder()
    builder.add_recipe_preset(first)
    builder.add_recipe_preset(alias)
    with pytest.raises(ValueError, match="are aliases"):
        builder.freeze(
            pack_dependencies={"content.neurodragon": frozenset()},
        )


def test_cross_pack_preset_requires_dependency_and_cannot_widen_visibility() -> None:
    cross_pack = _red_robe_preset(pack_id="custom.flavor")
    builder = _builder()
    builder.add_recipe_preset(cross_pack)
    with pytest.raises(ValueError, match="without a declared pack dependency"):
        builder.freeze(
            pack_dependencies={
                "content.neurodragon": frozenset(),
                "custom.flavor": frozenset(),
            },
        )

    builder = _builder()
    builder.add_recipe_preset(cross_pack)
    registry = builder.freeze(
        pack_dependencies={
            "content.neurodragon": frozenset(),
            "custom.flavor": frozenset({"content.neurodragon"}),
        },
    )
    assert registry.resolve_recipe_preset(cross_pack.ref) == cross_pack

    hidden_target = ROBES_DECLARATION.model_copy(
        update={
            "descriptor": ROBES_DECLARATION.descriptor.model_copy(
                update={"visibility": ContentVisibility.OBSERVED},
            ),
        },
    )
    builder = ContentRegistryBuilder()
    loaded = bootstrap_content_system()
    builder.add_source(
        loaded.registry.sources[
            ROBES_DECLARATION.provenance.primary_source_id
        ],
    )
    builder.add_declaration(hidden_target)
    builder.add_recipe_preset(_red_robe_preset())
    with pytest.raises(ValueError, match="more visible"):
        builder.freeze(
            pack_dependencies={"content.neurodragon": frozenset()},
        )


def test_pack_scanner_reads_only_the_explicit_preset_tuple() -> None:
    preset = _red_robe_preset()
    fixture_module = ModuleType("fixture_recipe_presets")
    setattr(fixture_module, "imported_but_not_exported", preset)
    sys.modules[fixture_module.__name__] = fixture_module
    try:
        assert scan_module_content_recipe_presets(fixture_module) == ()
        setattr(
            fixture_module,
            CONTENT_RECIPE_PRESETS_EXPORT,
            (preset,),
        )
        assert scan_module_content_recipe_presets(fixture_module) == (preset,)
    finally:
        del sys.modules[fixture_module.__name__]


def test_builtin_apparel_preset_inventory_is_exact_and_cataloged() -> None:
    expected_visual_ids = {
        "81000001",
        "81000003",
        "81000004",
        "81000005",
        "81000007",
        "81000008",
        "8100000b",
        "82000001",
        "82000009",
        "84000006",
        "85000004",
        "b0000002",
        "b0000003",
        "b0000004",
        "b0000005",
        "b0000007",
        "b0000008",
        "b0000009",
        "h0000008",
        "h0000011",
    }
    loaded = bootstrap_content_system()
    catalog = build_public_content_catalog(loaded)

    assert set(APPAREL_RECIPE_PRESETS_BY_VISUAL_VARIANT_ID) == (
        expected_visual_ids
    )
    assert tuple(APPAREL_RECIPE_PRESETS_BY_VISUAL_VARIANT_ID.values()) == (
        NEURODRAGON_APPAREL_RECIPE_PRESETS
    )
    apparel_preset_ids = {
        preset.ref.identity_key
        for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS
    }
    assert apparel_preset_ids <= set(loaded.registry.recipe_presets)
    assert apparel_preset_ids <= {
        preset.ref.identity_key
        for preset in catalog.presets
    }


def test_every_apparel_preset_materializes_its_exact_name_and_visual_identity() -> None:
    for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS:
        item = materialize_item(
            preset.recipe,
            uuid4(),
            origin=ItemRuntimeOrigin.STARTER,
        )
        assert item.name == preset.descriptor.display_name
        assert item.visual_variant_id == (
            preset.descriptor.presentation.visual_variant_key
        )
        assert item.content_ref == preset.recipe.ref


def test_every_named_apparel_variant_is_a_registered_preset() -> None:
    registered_digests = {
        preset.recipe.recipe_digest
        for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS
    }
    assert registered_digests == {
        preset.recipe.recipe_digest
        for preset in APPAREL_RECIPE_PRESETS_BY_VISUAL_VARIANT_ID.values()
    }


def test_consumers_do_not_recreate_aesthetic_recipes_ad_hoc() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    consumer_paths = (
        repository_root / "dnd" / "classes" / "content_factories.py",
        repository_root
        / "dnd"
        / "content_system"
        / "builtin_character_builds.py",
        repository_root / "dnd" / "premade_characters.py",
        repository_root / "dnd" / "monsters" / "bestiary_content.py",
    )

    for path in consumer_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visual_recipe_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "create"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ContentRecipe"
            ):
                continue
            if any(
                keyword.arg == "parameters"
                and isinstance(keyword.value, ast.Dict)
                and any(
                    isinstance(key, ast.Constant)
                    and key.value == "visual_variant_id"
                    for key in keyword.value.keys
                )
                for keyword in node.keywords
            ):
                visual_recipe_calls.append(node.lineno)
        assert visual_recipe_calls == [], (
            f"{path} recreates visual recipes at lines {visual_recipe_calls}"
        )
