"""Maintained materialization proof for direct creature possessions."""

from uuid import uuid4

import pytest

from dnd.classes.content_factories import PLAYER_CLASS_CREATURE_RECIPES_BY_ID
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _reset_engine():
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize(
    ("creature_id", "recipe"),
    tuple(BESTIARY_CREATURE_RECIPES_BY_ID.items())
    + tuple(PLAYER_CLASS_CREATURE_RECIPES_BY_ID.items()),
)
@pytest.mark.parametrize("possession_mode", tuple(CreaturePossessionMode))
def test_all_eleven_roots_materialize_both_possession_modes(
    creature_id: str,
    recipe: ContentRecipe,
    possession_mode: CreaturePossessionMode,
) -> None:
    """All roots construct, and default mode installs direct possessions."""
    entity = materialize_creature(
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
    assert entity.content_ref == recipe.ref
    assert entity.uuid == entity.source_entity_uuid
    assert entity.registered_actions
    items = (
        *entity.equipment.get_all_equipped_items(),
        *entity.inventory.items.values(),
    )
    assert all(item.item_id for item in items)
    if possession_mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS:
        assert items
