"""Canonical coverage for active bestiary and generic class creature roots."""

from __future__ import annotations

import ast
from collections.abc import Callable, Generator
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest

from dnd.classes.content_factories import (
    PLAYER_CLASS_CREATURE_DECLARATIONS,
    PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID,
    PLAYER_CLASS_CREATURE_RECIPES_BY_ID,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.entity import Entity
from dnd.monsters.bestiary import (
    create_caster,
    create_goblin,
    create_goblin_archer,
    create_skeleton,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
)
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS,
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
    BESTIARY_CREATURE_RECIPES_BY_ID,
)
from dnd.monsters.bestiary_items import (
    ARMOR_SCRAPS_DECLARATION,
    ARMOR_SCRAPS_RECIPE,
)
from dnd.runtime_reset import reset_engine_runtime


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BESTIARY_IDS = (
    "goblin",
    "skeleton",
    "goblin_archer",
    "generic_caster",
    "skeleton_warrior",
    "skeleton_archer",
    "skeleton_warlock",
)
EXPECTED_PLAYER_CLASS_IDS = ("barbarian", "fighter", "sorcerer")


@pytest.fixture(scope="module", autouse=True)
def _install_complete_content_system() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(
        bootstrap_content_system(pack_roots=()),
    )


@pytest.fixture(autouse=True)
def _reset_engine() -> Generator[None, None, None]:
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


def _materialize(
    creature_id: str,
    recipe: ContentRecipe,
    possession_mode: CreaturePossessionMode,
) -> Entity:
    return materialize_creature(
        recipe,
        runtime_entity_uuid=uuid4(),
        display_name=f"Canonical {creature_id}",
        faction="tests",
        position=(3, 4),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.remaining_creatures.{creature_id}",
        ),
        possession_mode=possession_mode,
    )


def _semantic_snapshot(entity: Entity) -> dict[str, object]:
    """Capture mechanics while excluding fresh runtime identities."""
    abilities = entity.ability_scores
    equipped = tuple(sorted(
        (
            item.equipped_slot,
            item.name,
            item.stack_count,
            (
                item.content_ref.identity_key
                if item.content_ref is not None
                else None
            ),
        )
        for item in entity.equipment.get_all_equipped_items()
    ))
    inventory = tuple(sorted(
        (
            item.name,
            item.stack_count,
            (
                item.content_ref.identity_key
                if item.content_ref is not None
                else None
            ),
        )
        for item in entity.inventory.items.values()
    ))
    return {
        "name": entity.name,
        "position": entity.position,
        "faction": entity.faction,
        "weight": entity.weight,
        "size": entity.size,
        "creature_type": entity.creature_type,
        "hp": entity.get_hp(),
        "max_hp": entity.get_max_hp(),
        "ac": entity.ac_bonus().normalized_score,
        "proficiency": entity.proficiency_bonus.normalized_score,
        "abilities": (
            abilities.strength.ability_score.normalized_score,
            abilities.dexterity.ability_score.normalized_score,
            abilities.constitution.ability_score.normalized_score,
            abilities.intelligence.ability_score.normalized_score,
            abilities.wisdom.ability_score.normalized_score,
            abilities.charisma.ability_score.normalized_score,
        ),
        "movement": entity.action_economy.movement.normalized_score,
        "actions": tuple(sorted(
            (
                type(action).__name__,
                action.name,
                action.action_category.value,
                action.target_type.value,
            )
            for action in entity.registered_actions
        )),
        "conditions": tuple(sorted(entity.active_conditions)),
        "condition_immunities": tuple(sorted(entity.condition_immunities)),
        "senses": tuple(sorted(
            (mode.sense_type.value, mode.range_feet)
            for mode in entity.senses.sense_modes
        )),
        "equipped": equipped,
        "inventory": inventory,
    }


def _compare_legacy_and_canonical(
    legacy_builder: Callable[[], Entity],
    creature_id: str,
    recipe: ContentRecipe,
) -> None:
    legacy = legacy_builder()
    legacy_snapshot = _semantic_snapshot(legacy)
    reset_engine_runtime(grid_size=(12, 12))
    canonical = _materialize(
        creature_id,
        recipe,
        CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    assert _semantic_snapshot(canonical) == {
        **legacy_snapshot,
        "name": f"Canonical {creature_id}",
        "position": (3, 4),
        "faction": "tests",
    }


def test_registry_maps_are_exact_immutable_and_context_free() -> None:
    """Ten roots have one authenticated recipe and no ephemeral parameters."""
    assert tuple(BESTIARY_CREATURE_DECLARATIONS_BY_ID) == EXPECTED_BESTIARY_IDS
    assert tuple(BESTIARY_CREATURE_RECIPES_BY_ID) == EXPECTED_BESTIARY_IDS
    assert tuple(PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID) == (
        EXPECTED_PLAYER_CLASS_IDS
    )
    assert tuple(PLAYER_CLASS_CREATURE_RECIPES_BY_ID) == (
        EXPECTED_PLAYER_CLASS_IDS
    )
    assert isinstance(BESTIARY_CREATURE_DECLARATIONS_BY_ID, MappingProxyType)
    assert isinstance(BESTIARY_CREATURE_RECIPES_BY_ID, MappingProxyType)
    assert isinstance(
        PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID,
        MappingProxyType,
    )
    assert isinstance(PLAYER_CLASS_CREATURE_RECIPES_BY_ID, MappingProxyType)
    assert BESTIARY_CREATURE_DECLARATIONS == tuple(
        BESTIARY_CREATURE_DECLARATIONS_BY_ID.values(),
    )
    assert PLAYER_CLASS_CREATURE_DECLARATIONS == tuple(
        PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID.values(),
    )

    for declaration in (
        *BESTIARY_CREATURE_DECLARATIONS,
        *PLAYER_CLASS_CREATURE_DECLARATIONS,
    ):
        assert declaration.ref.definition_kind == ContentDefinitionKind.CREATURE
        assert declaration.construction is not None
        fields = declaration.construction.parameter_model.model_fields
        assert {"name", "position", "faction"}.isdisjoint(fields)


def test_bootstrap_closes_every_recipe_and_dependency_without_lazy_imports() -> None:
    """Hosted startup sees all declarations before any creature is built."""
    loaded = bootstrap_content_system(pack_roots=())
    registry = loaded.registry
    declarations = (
        ARMOR_SCRAPS_DECLARATION,
        *BESTIARY_CREATURE_DECLARATIONS,
        *PLAYER_CLASS_CREATURE_DECLARATIONS,
    )
    for declaration in declarations:
        assert registry.resolve_factory(declaration.ref) == declaration
        for dependency in declaration.dependencies:
            assert registry.resolve_definition(dependency.target_ref) is not None

    bestiary_tree = ast.parse(
        (REPOSITORY_ROOT / "dnd/monsters/bestiary.py").read_text(
            encoding="utf-8",
        ),
    )
    imported_modules = {
        node.module
        for node in ast.walk(bestiary_tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "dnd.content_system.item_materialization" not in imported_modules
    assert (
        "dnd.content_system.item_runtime_materialization"
        in imported_modules
    )


@pytest.mark.parametrize(
    ("creature_id", "recipe"),
    tuple(BESTIARY_CREATURE_RECIPES_BY_ID.items())
    + tuple(PLAYER_CLASS_CREATURE_RECIPES_BY_ID.items()),
)
@pytest.mark.parametrize("possession_mode", tuple(CreaturePossessionMode))
def test_all_ten_roots_materialize_both_possession_modes(
    creature_id: str,
    recipe: ContentRecipe,
    possession_mode: CreaturePossessionMode,
) -> None:
    """Structure-only keeps behavior and default mode preserves possessions."""
    entity = _materialize(creature_id, recipe, possession_mode)
    assert entity.content_ref == recipe.ref
    assert entity.uuid == entity.source_entity_uuid
    assert entity.registered_actions
    if possession_mode == CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY:
        assert entity.equipment.get_all_equipped_items() == []
        assert entity.inventory.items == {}
    else:
        assert (
            entity.equipment.get_all_equipped_items()
            or entity.inventory.items
        )


@pytest.mark.parametrize(
    ("legacy_builder", "creature_id", "recipe"),
    (
        (
            lambda: create_goblin(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "goblin",
            BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        ),
        (
            lambda: create_skeleton(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "skeleton",
            BESTIARY_CREATURE_RECIPES_BY_ID["skeleton"],
        ),
        (
            lambda: create_goblin_archer(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "goblin_archer",
            BESTIARY_CREATURE_RECIPES_BY_ID["goblin_archer"],
        ),
        (
            lambda: create_caster(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "generic_caster",
            BESTIARY_CREATURE_RECIPES_BY_ID["generic_caster"],
        ),
        (
            lambda: create_skeleton_warrior(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "skeleton_warrior",
            BESTIARY_CREATURE_RECIPES_BY_ID["skeleton_warrior"],
        ),
        (
            lambda: create_skeleton_archer(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "skeleton_archer",
            BESTIARY_CREATURE_RECIPES_BY_ID["skeleton_archer"],
        ),
        (
            lambda: create_skeleton_warlock(
                name="Legacy",
                position=(3, 4),
                faction="tests",
            ),
            "skeleton_warlock",
            BESTIARY_CREATURE_RECIPES_BY_ID["skeleton_warlock"],
        ),
    ),
)
def test_bestiary_catalog_roots_match_the_existing_constructors(
    legacy_builder: Callable[[], Entity],
    creature_id: str,
    recipe: ContentRecipe,
) -> None:
    """The bestiary registry cut preserves its constructor semantics."""
    _compare_legacy_and_canonical(legacy_builder, creature_id, recipe)


def test_armor_scraps_is_one_persistent_content_possession() -> None:
    """Skeleton armor no longer bypasses the item registry."""
    assert ARMOR_SCRAPS_RECIPE.ref == ARMOR_SCRAPS_DECLARATION.ref
    for creature_id in (
        "skeleton",
        "skeleton_warrior",
        "skeleton_archer",
        "skeleton_warlock",
    ):
        declaration = BESTIARY_CREATURE_DECLARATIONS_BY_ID[creature_id]
        assert ARMOR_SCRAPS_RECIPE.ref.identity_key in {
            dependency.target_ref.identity_key
            for dependency in declaration.dependencies
        }
