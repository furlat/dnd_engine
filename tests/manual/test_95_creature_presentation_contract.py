"""Creature presentation and equipment visual-contract tests."""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import EquippedVisualPolicy
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.creature_types import CreatureType, Size
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY,
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
    BESTIARY_CREATURE_RECIPES_BY_ID,
)
from dnd.items.apparel_presets import (
    DARK_CLOTH_SHOES_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from server.world_projection import project_entity_summary, project_equipment_overview


VISUAL_SCALE_BY_SIZE = {
    Size.TINY: 0.68,
    Size.SMALL: 0.82,
    Size.MEDIUM: 1.0,
    Size.LARGE: 1.28,
    Size.HUGE: 1.55,
    Size.GARGANTUAN: 2.0,
}
DIRECT_VISUAL_ALIASES = {
    "Sling": "Sling",
    "Hand Crossbow": "Light Crossbow",
    "Thrown Dagger": "Dagger",
    "Thrown Javelin": "Javelin",
    "Morningstar": "Morningstar",
    "Greatclub": "Club",
}
BODY_DRIVEN_ITEMS = {"Natural Armor", "Bite", "Claws", "Slam"}


@pytest.fixture(autouse=True)
def reset_presentation_state() -> None:
    """Clear engine registries before each presentation test."""
    _reset_state()


def _reset_state() -> None:
    """Create an isolated map for monster factories."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 20, 20)


def _materialize_srd_fixture(creature_id: str) -> Entity:
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.creature_presentation.{creature_id}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def test_preset_goblin_and_skeleton_keep_layered_presentation() -> None:
    """Equipment-driven humanoids and existing skeleton art stay layered."""
    goblin = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=uuid4(),
        display_name="Goblin",
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.creature_presentation.goblin",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    skeleton = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["skeleton"],
        runtime_entity_uuid=uuid4(),
        display_name="Skeleton",
        faction="monsters",
        position=(4, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.creature_presentation.skeleton",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )

    goblin_api = project_entity_summary(goblin)
    skeleton_api = project_entity_summary(skeleton)

    assert goblin_api.content_ref.model_dump(mode="json") == (
        BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref.model_dump(
            mode="json",
        )
    )
    assert skeleton_api.content_ref.model_dump(mode="json") == (
        BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref.model_dump(
            mode="json",
        )
    )
    assert goblin_api.creature_type == CreatureType.HUMANOID.value
    assert goblin_api.size == Size.SMALL.value
    assert goblin_api.appearance.presentation_kind == "layered"
    assert goblin_api.appearance.visual_scale == pytest.approx(0.82)
    assert goblin_api.appearance.visual_scale_x == 1.0
    assert skeleton_api.creature_type == CreatureType.UNDEAD.value
    assert skeleton_api.appearance.presentation_kind == "layered"
    assert skeleton_api.appearance.body_category == "NakedBody2"


def test_complete_bestiary_projects_its_exact_authored_identity() -> None:
    """Every active bestiary factory survives materialization and projection."""
    for creature_id, declaration in BESTIARY_CREATURE_DECLARATIONS_BY_ID.items():
        _reset_state()
        entity = materialize_creature(
            BESTIARY_CREATURE_RECIPES_BY_ID[creature_id],
            runtime_entity_uuid=uuid4(),
            display_name=declaration.descriptor.display_name,
            faction="monsters",
            position=(2, 2),
            deployment_role=CreatureDeploymentRole(
                role_id=f"tests.creature_identity.{creature_id}",
            ),
            possession_mode=(
                CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
            ),
        )

        assert project_entity_summary(entity).content_ref.model_dump(
            mode="json",
        ) == declaration.ref.model_dump(mode="json")


def test_goblin_caster_owns_its_authored_default_wardrobe() -> None:
    """Raw creature materialization cannot rely on a scenario-only wardrobe."""
    entity = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin_caster"],
        runtime_entity_uuid=uuid4(),
        display_name="Goblin Caster",
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id="tests.creature_presentation.goblin_caster",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )

    assert entity.equipment.body_armor is not None
    assert entity.equipment.body_armor.content_ref == (
        HEDGE_WIZARD_ROBE_PRESET.recipe.ref
    )
    assert ITEM_RUNTIME_BINDINGS.require(
        entity.equipment.body_armor.uuid
    ).recipe == HEDGE_WIZARD_ROBE_PRESET.recipe
    assert entity.equipment.boots is not None
    assert entity.equipment.boots.content_ref == (
        DARK_CLOTH_SHOES_PRESET.recipe.ref
    )
    assert ITEM_RUNTIME_BINDINGS.require(
        entity.equipment.boots.uuid
    ).recipe == DARK_CLOTH_SHOES_PRESET.recipe
    equipped_dependencies = {
        dependency.target_ref.identity_key
        for dependency in BESTIARY_CREATURE_DECLARATIONS_BY_ID[
            "goblin_caster"
        ].dependencies
        if dependency.relation == ContentDependencyRelation.EQUIPS_ITEM
    }
    assert HEDGE_WIZARD_ROBE_PRESET.recipe.ref.identity_key in (
        equipped_dependencies
    )
    assert DARK_CLOTH_SHOES_PRESET.recipe.ref.identity_key in (
        equipped_dependencies
    )


@pytest.mark.parametrize(
    ("wardrobe_key", "creature_id", "parameters"),
    (
        ("goblin", "goblin", {}),
        ("goblin_archer", "goblin_archer", {}),
        (
            "generic_caster.arcane",
            "generic_caster",
            {"level": 5, "wardrobe": "arcane"},
        ),
        (
            "generic_caster.dark",
            "generic_caster",
            {"level": 5, "wardrobe": "dark"},
        ),
        (
            "generic_caster.divine",
            "generic_caster",
            {"level": 5, "wardrobe": "divine"},
        ),
        (
            "generic_caster.necromancer",
            "generic_caster",
            {"level": 5, "wardrobe": "necromancer"},
        ),
        ("goblin_caster", "goblin_caster", {}),
    ),
)
def test_bestiary_roots_own_every_authored_wardrobe_variant(
    wardrobe_key: str,
    creature_id: str,
    parameters: dict[str, object],
) -> None:
    """Every production bestiary wardrobe is a factory-owned exact grant."""
    declaration = BESTIARY_CREATURE_DECLARATIONS_BY_ID[creature_id]
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters=parameters,
    )
    entity = materialize_creature(
        recipe,
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.creature_wardrobe.{wardrobe_key}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    expected = BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY[wardrobe_key]
    equipped_digests = {
        ITEM_RUNTIME_BINDINGS.require(item.uuid).recipe.recipe_digest
        for item in entity.equipment.get_all_equipped_items()
    }
    assert {
        grant.recipe.recipe_digest
        for grant in expected
    } <= equipped_digests
    declared_equipment_refs = {
        dependency.target_ref
        for dependency in declaration.dependencies
        if dependency.relation is ContentDependencyRelation.EQUIPS_ITEM
    }
    assert {
        grant.recipe.ref
        for grant in expected
    } <= declared_equipment_refs


def test_srd_roster_uses_explicit_type_driven_presentation() -> None:
    """SRD factories select presentation from typed creature data, not names."""
    for creature_id in SRD_CREATURE_RECIPES_BY_ID:
        _reset_state()
        entity = _materialize_srd_fixture(creature_id)
        summary = project_entity_summary(entity)
        expected_kind = "layered" if entity.creature_type == CreatureType.HUMANOID else "placeholder"

        assert summary.content_ref.model_dump(mode="json") == (
            SRD_CREATURE_DECLARATIONS_BY_ID[creature_id].ref.model_dump(
                mode="json",
            )
        )
        assert summary.creature_type == entity.creature_type.value
        assert summary.size == entity.size.value
        assert summary.appearance.presentation_kind == expected_kind
        assert summary.appearance.visual_scale == pytest.approx(VISUAL_SCALE_BY_SIZE[entity.size])
        assert summary.appearance.visual_scale_x == 1.0
        if expected_kind == "placeholder":
            assert summary.appearance.placeholder_tint == 0x36FF62


def test_player_projection_rejects_an_unattributed_entity() -> None:
    """Player transport never falls back to a name-derived creature identity."""
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Unattributed fixture",
    )

    with pytest.raises(ValueError, match="no exact authored creature identity"):
        project_entity_summary(entity)


def test_srd_equipment_exposes_a_complete_visual_contract() -> None:
    """Every equipped SRD item is either visibly keyed or explicitly body-driven."""
    observed_aliases: dict[str, str] = {}
    observed_body_items: set[str] = set()

    for creature_id in SRD_CREATURE_RECIPES_BY_ID:
        _reset_state()
        entity = _materialize_srd_fixture(creature_id)
        overview = project_equipment_overview(entity)

        for slot in overview.slots:
            item = slot.item
            if item is None:
                continue
            assert item.visual_item_name
            if item.name in DIRECT_VISUAL_ALIASES:
                assert item.equipped_visual_policy == EquippedVisualPolicy.VISIBLE.value
                observed_aliases[item.name] = item.visual_item_name
            if item.name in BODY_DRIVEN_ITEMS:
                assert item.equipped_visual_policy == EquippedVisualPolicy.HIDDEN.value
                observed_body_items.add(item.name)

    assert observed_aliases == DIRECT_VISUAL_ALIASES
    assert observed_body_items == BODY_DRIVEN_ITEMS
