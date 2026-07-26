"""Approved premades become exact durable character and holdings revisions."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.premade_characters import PREMADE_CHARACTER_TEMPLATES
from server.character_composition import (
    PremadeCharacterNotFoundError,
    compose_premade_character_bootstrap,
)
from server.game_gateway_models import CreateCharacterRequest


@pytest.mark.parametrize("premade_id", tuple(PREMADE_CHARACTER_TEMPLATES))
def test_every_approved_premade_composes_exact_revision_one(
    premade_id: str,
) -> None:
    """All starter rows are exact durable possession recipes, never live state."""

    content_system = bootstrap_content_system()
    character_id = uuid4()
    principal_id = uuid4()

    first = compose_premade_character_bootstrap(
        character_id=character_id,
        owner_principal_id=principal_id,
        display_name="Persistent Hero",
        premade_id=premade_id,
        content_system=content_system,
    )
    second = compose_premade_character_bootstrap(
        character_id=character_id,
        owner_principal_id=principal_id,
        display_name="Persistent Hero",
        premade_id=premade_id,
        content_system=content_system,
    )

    template = PREMADE_CHARACTER_TEMPLATES[premade_id]
    assert first == second
    assert first.definition.creature_recipe == template.creature_recipe
    assert first.definition.premade_id == premade_id
    assert first.definition.content_set_digest == content_system.content_set_digest
    assert first.definition.definition_revision == 1
    assert first.starter_holdings.holdings_revision == 1
    assert len(first.starter_holdings.items) == len(template.starter_holdings)
    assert tuple(
        item.character_item_id for item in first.starter_holdings.items
    ) == tuple(
        sorted(
            (
                item.character_item_id
                for item in first.starter_holdings.items
            ),
            key=lambda item_id: item_id.hex,
        ),
    )
    assert len({
        item.character_item_id
        for item in first.starter_holdings.items
    }) == len(first.starter_holdings.items)
    for item in first.starter_holdings.items:
        declaration = content_system.registry.resolve_factory(item.recipe.ref)
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )


def test_character_identity_namespaces_deterministic_starter_item_ids() -> None:
    """Two characters of one premade never share persistent item identities."""

    content_system = bootstrap_content_system()
    principal_id = uuid4()
    premade_id = next(iter(PREMADE_CHARACTER_TEMPLATES))
    first = compose_premade_character_bootstrap(
        character_id=uuid4(),
        owner_principal_id=principal_id,
        display_name="First",
        premade_id=premade_id,
        content_system=content_system,
    )
    second = compose_premade_character_bootstrap(
        character_id=uuid4(),
        owner_principal_id=principal_id,
        display_name="Second",
        premade_id=premade_id,
        content_system=content_system,
    )

    assert {
        item.character_item_id for item in first.starter_holdings.items
    }.isdisjoint({
        item.character_item_id for item in second.starter_holdings.items
    })


def test_unknown_premade_fails_before_any_directory_write() -> None:
    """The public selector cannot submit an arbitrary creature recipe."""

    with pytest.raises(PremadeCharacterNotFoundError):
        compose_premade_character_bootstrap(
            character_id=uuid4(),
            owner_principal_id=uuid4(),
            display_name="Unknown",
            premade_id="hero.unknown",
            content_system=bootstrap_content_system(),
        )


def test_public_character_creation_has_no_legacy_preset_or_recipe_path() -> None:
    """Clients submit one approved premade ID, never duplicate factory authority."""

    request = CreateCharacterRequest(
        display_name="Canonical",
        premade_id="hero.fighter_l5_shield_torch",
    )
    assert request.model_dump() == {
        "display_name": "Canonical",
        "premade_id": "hero.fighter_l5_shield_torch",
    }
    with pytest.raises(ValidationError):
        CreateCharacterRequest.model_validate(
            {
                "display_name": "Legacy",
                "preset_configuration_id": (
                    "hero.fighter_l5_shield_torch"
                ),
            },
        )
