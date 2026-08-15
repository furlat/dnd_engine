"""Premade character values materialize without a profile or database."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    DEFAULT_CHARACTER_RULESET_DIGEST,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.types.equipment import BodyPart
from dnd.core.gridmap import get_map
from dnd.items.torches import Torch
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    reset_engine_runtime(grid_size=(15, 15))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("premade_id", tuple(BUILTIN_PREMADE_BUILDS))
def test_premade_materializes_from_authored_revisions_only(
    premade_id: str,
) -> None:
    """Runtime structure and possessions consume only composed value objects."""
    character_id = uuid4()
    revisions = compose_builtin_character_revisions(
        character_id=character_id,
        build=BUILTIN_PREMADE_BUILDS[premade_id],
        content_system=SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )

    result = materialize_character(
        definition=revisions.definition,
        holdings=revisions.holdings,
        loadout=revisions.loadout,
        runtime_entity_uuid=uuid4(),
        display_name="Premade Hero",
        faction="heroes",
        position=(2, 3),
        deployment_role=CreatureDeploymentRole(role_id="party.hero"),
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
    )

    assert result.entity.content_ref == revisions.definition.body_recipe.ref
    assert result.entity.name == "Premade Hero"
    assert len(result.item_lineage) == len(revisions.holdings.items)
    assert {item_id for item_id, _ in result.item_lineage} == {
        item.character_item_id for item in revisions.holdings.items
    }
    assert {
        binding.character_item_id
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
        if binding.character_item_id is not None
    } == {
        item.character_item_id for item in revisions.holdings.items
    }
    torches = tuple(
        item
        for item in result.entity.inventory.items.values()
        if isinstance(item, Torch)
    )
    assert len(torches) == 1
    assert torches[0].is_lit
    assert torches[0]._light_source_uuid in get_map()._light_sources

    if premade_id == "hero.fighter_2_sorcerer_3_spellblade":
        helmet = result.entity.equipment.helmet
        assert helmet is not None
        charisma = result.entity.ability_scores.charisma.ability_score
        assert charisma.score == 18
        assert result.entity.equipment.unequip(BodyPart.HEAD) is helmet
        assert charisma.score == 15
        assert result.entity.equipment.equip(helmet, BodyPart.HEAD)
        assert charisma.score == 18


def test_materialization_rejects_a_changed_ruleset_identity() -> None:
    revisions = compose_builtin_character_revisions(
        character_id=uuid4(),
        build=next(iter(BUILTIN_PREMADE_BUILDS.values())),
        content_system=SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )

    with pytest.raises(ValueError, match="ruleset"):
        materialize_character(
            definition=revisions.definition,
            holdings=revisions.holdings,
            loadout=revisions.loadout,
            runtime_entity_uuid=uuid4(),
            display_name="Rejected Hero",
            faction="heroes",
            position=(2, 3),
            deployment_role=CreatureDeploymentRole(role_id="party.hero"),
            expected_ruleset_digest="f" * 64,
        )
