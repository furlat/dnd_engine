"""Durable characters reconstruct structure and possessions through one path."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
)
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevision,
    CharacterHoldingsRevision,
)
from dnd.core.content.materialization import CreatureDeploymentRole
from dnd.premade_characters import PREMADE_CHARACTER_TEMPLATES
from dnd.runtime_reset import reset_engine_runtime
from server.character_composition import compose_premade_character_bootstrap


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    reset_engine_runtime(grid_size=(15, 15))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("premade_id", tuple(PREMADE_CHARACTER_TEMPLATES))
def test_premade_deployment_uses_only_persisted_holdings(
    premade_id: str,
) -> None:
    """Structural factories cannot regenerate a second starter loadout."""

    bootstrap = compose_premade_character_bootstrap(
        character_id=uuid4(),
        owner_principal_id=uuid4(),
        display_name="Durable Hero",
        premade_id=premade_id,
        content_system=SERVER_CONTENT_SYSTEM_RUNTIME.require(),
    )
    result = materialize_character(
        definition=bootstrap.definition,
        holdings=bootstrap.starter_holdings,
        runtime_entity_uuid=uuid4(),
        display_name=bootstrap.display_name,
        faction="heroes",
        position=(2, 3),
        deployment_role=CreatureDeploymentRole(
            role_id="hosted.side_a.character",
        ),
    )

    assert result.entity.content_ref == bootstrap.definition.creature_recipe.ref
    assert result.entity.name == "Durable Hero"
    assert len(result.item_lineage) == len(bootstrap.starter_holdings.items)
    assert {character_item_id for character_item_id, _ in result.item_lineage} == {
        item.character_item_id for item in bootstrap.starter_holdings.items
    }
    assert {
        binding.character_item_id
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
        if binding.character_item_id is not None
    } == {
        item.character_item_id for item in bootstrap.starter_holdings.items
    }
    assert all(
        binding.origin.value == "persisted"
        for binding in ITEM_RUNTIME_BINDINGS.bindings.values()
    )


def test_worker_rejects_character_from_another_content_set() -> None:
    """A stored definition cannot silently resolve under changed installed code."""

    loaded = bootstrap_content_system()
    bootstrap = compose_premade_character_bootstrap(
        character_id=uuid4(),
        owner_principal_id=uuid4(),
        display_name="Pinned Hero",
        premade_id=next(iter(PREMADE_CHARACTER_TEMPLATES)),
        content_system=loaded,
    )
    changed_definition = CharacterDefinitionRevision.create(
        character_id=bootstrap.character_id,
        definition_revision=1,
        creature_recipe=bootstrap.definition.creature_recipe,
        premade_id=bootstrap.definition.premade_id,
        content_set_digest="f" * 64,
    )

    with pytest.raises(ValueError, match="content set differs"):
        materialize_character(
            definition=changed_definition,
            holdings=bootstrap.starter_holdings,
            runtime_entity_uuid=uuid4(),
            display_name="Pinned Hero",
            faction="heroes",
            position=(1, 1),
            deployment_role=CreatureDeploymentRole(
                role_id="hosted.side_a.character",
            ),
        )


def test_definition_and_holdings_character_identity_must_match() -> None:
    """A valid revision from another character cannot be spliced into launch."""

    loaded = bootstrap_content_system()
    first = compose_premade_character_bootstrap(
        character_id=uuid4(),
        owner_principal_id=uuid4(),
        display_name="First",
        premade_id=next(iter(PREMADE_CHARACTER_TEMPLATES)),
        content_system=loaded,
    )
    mismatched = CharacterHoldingsRevision.create(
        character_id=uuid4(),
        holdings_revision=1,
        items=(),
    )

    with pytest.raises(ValueError, match="different characters"):
        materialize_character(
            definition=first.definition,
            holdings=mismatched,
            runtime_entity_uuid=uuid4(),
            display_name="First",
            faction="heroes",
            position=(1, 1),
            deployment_role=CreatureDeploymentRole(
                role_id="hosted.side_a.character",
            ),
        )
