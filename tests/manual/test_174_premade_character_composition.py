"""Approved premades compose exact database-free character revisions."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_revisions,
    starter_holdings_for_build,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE


@pytest.mark.parametrize("premade_id", tuple(BUILTIN_PREMADE_BUILDS))
def test_every_approved_premade_composes_exact_schema2_revision_one(
    premade_id: str,
) -> None:
    """Every premade is a complete value graph, not a database template."""
    content_system = bootstrap_content_system()
    character_id = uuid4()
    build = BUILTIN_PREMADE_BUILDS[premade_id]

    first = compose_builtin_character_revisions(
        character_id=character_id,
        build=build,
        content_system=content_system,
    )
    second = compose_builtin_character_revisions(
        character_id=character_id,
        build=build,
        content_system=content_system,
    )

    assert first == second
    assert first.definition.schema_version == 2
    assert first.definition.character_id == character_id
    assert first.definition.body_recipe == PLAYER_CHARACTER_BODY_RECIPE
    assert first.definition.premade_id == premade_id
    assert first.definition.definition_revision == 1
    assert first.definition.earned_character_level == build.level
    assert len(first.definition.class_levels) == build.level
    assert first.holdings.holdings_revision == 1
    assert len(first.holdings.items) == len(starter_holdings_for_build(build))
    assert first.loadout.loadout_revision == 1
    assert first.loadout.based_on_definition_revision == 1
    assert tuple(
        item.character_item_id for item in first.holdings.items
    ) == tuple(sorted(
        (item.character_item_id for item in first.holdings.items),
        key=lambda item_id: item_id.hex,
    ))
    for item in first.holdings.items:
        declaration = content_system.registry.resolve_factory(item.recipe.ref)
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )


def test_character_identity_namespaces_deterministic_starter_item_ids() -> None:
    """Two premades of one build never share possession identities."""
    content_system = bootstrap_content_system()
    build = next(iter(BUILTIN_PREMADE_BUILDS.values()))
    first = compose_builtin_character_revisions(
        character_id=uuid4(),
        build=build,
        content_system=content_system,
    )
    second = compose_builtin_character_revisions(
        character_id=uuid4(),
        build=build,
        content_system=content_system,
    )

    assert {
        item.character_item_id for item in first.holdings.items
    }.isdisjoint({
        item.character_item_id for item in second.holdings.items
    })
