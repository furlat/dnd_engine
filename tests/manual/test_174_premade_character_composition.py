"""Approved premades become exact durable character and holdings revisions."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    starter_holdings_for_build,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.player_character_body import PLAYER_CHARACTER_BODY_RECIPE
from server.character_directory_contracts import CreateCharacterRequest
from server.character_directory_service import (
    CharacterDirectoryBuildError,
    CharacterDirectoryService,
)
from server.game_directory.contracts import (
    PrincipalCreate,
    PrincipalKind,
    PrincipalRecord,
)
from server.game_directory.repository import GameDirectoryRepository


PEPPER = b"premade-composition-test-pepper"


def _directory(
    database_path: Path,
) -> tuple[
    GameDirectoryRepository,
    CharacterDirectoryService,
    PrincipalRecord,
]:
    repository = GameDirectoryRepository(
        database_path,
        capability_pepper=PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Premade Owner",
        ),
    )
    return (
        repository,
        CharacterDirectoryService(
            repository,
            bootstrap_content_system(),
        ),
        owner,
    )


def _request_for_premade(
    service: CharacterDirectoryService,
    *,
    owner_id: UUID,
    premade_id: str,
    display_name: str,
) -> CreateCharacterRequest:
    premade = next(
        row
        for row in service.build_creation_catalog().premades
        if row.premade_id == premade_id
    )
    settings = service.ensure_profile_settings(owner_id)
    return CreateCharacterRequest(
        display_name=display_name,
        build=premade.build,
        loadout=premade.loadout,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=settings.ruleset_digest,
        idempotency_key=uuid4(),
    )


@pytest.mark.parametrize("premade_id", tuple(BUILTIN_PREMADE_BUILDS))
def test_every_approved_premade_composes_exact_schema2_revision_one(
    tmp_path: Path,
    premade_id: str,
) -> None:
    """All starter rows are exact durable possession recipes, never live state."""

    repository, service, owner = _directory(
        tmp_path / f"{premade_id}.sqlite3",
    )
    request = _request_for_premade(
        service,
        owner_id=owner.principal_id,
        premade_id=premade_id,
        display_name="Persistent Hero",
    )
    first = service.create_character(owner.principal_id, request)
    second = service.create_character(owner.principal_id, request)

    build = BUILTIN_PREMADE_BUILDS[premade_id]
    definition = first.definition.definition
    holdings = first.holdings.holdings
    loadout = first.loadout.loadout
    assert first == second
    assert definition.schema_version == 2
    assert definition.body_recipe == PLAYER_CHARACTER_BODY_RECIPE
    assert definition.premade_id == premade_id
    assert (
        definition.content_set_digest
        == service.content_system.content_set_digest
    )
    assert definition.definition_revision == 1
    assert definition.earned_character_level == build.level
    assert len(definition.class_levels) == build.level
    assert holdings.holdings_revision == 1
    assert len(holdings.items) == len(
        starter_holdings_for_build(build),
    )
    assert loadout.based_on_definition_revision == 1
    assert tuple(
        award.level_delta for award in first.advancement.awards
    ) == (build.level,)
    assert tuple(
        item.character_item_id for item in holdings.items
    ) == tuple(
        sorted(
            (
                item.character_item_id
                for item in holdings.items
            ),
            key=lambda item_id: item_id.hex,
        ),
    )
    assert len({
        item.character_item_id
        for item in holdings.items
    }) == len(holdings.items)
    for item in holdings.items:
        declaration = service.content_system.registry.resolve_factory(
            item.recipe.ref,
        )
        assert declaration.item_definition is not None
        assert (
            declaration.item_definition.persistence_policy
            is ItemPersistencePolicy.POSSESSION
        )
    repository.close()


def test_character_identity_namespaces_deterministic_starter_item_ids(
    tmp_path: Path,
) -> None:
    """Two characters of one premade never share persistent item identities."""

    repository, service, owner = _directory(tmp_path / "identities.sqlite3")
    premade_id = next(iter(BUILTIN_PREMADE_BUILDS))
    first = service.create_character(
        owner.principal_id,
        _request_for_premade(
            service,
            owner_id=owner.principal_id,
            premade_id=premade_id,
            display_name="First",
        ),
    )
    second = service.create_character(
        owner.principal_id,
        _request_for_premade(
            service,
            owner_id=owner.principal_id,
            premade_id=premade_id,
            display_name="Second",
        ),
    )

    assert {
        item.character_item_id
        for item in first.holdings.holdings.items
    }.isdisjoint({
        item.character_item_id
        for item in second.holdings.holdings.items
    })
    repository.close()


def test_unknown_premade_fails_before_any_directory_write(
    tmp_path: Path,
) -> None:
    """The public selector cannot submit an arbitrary creature recipe."""

    repository, service, owner = _directory(tmp_path / "unknown.sqlite3")
    known_id = next(iter(BUILTIN_PREMADE_BUILDS))
    known = _request_for_premade(
        service,
        owner_id=owner.principal_id,
        premade_id=known_id,
        display_name="Unknown",
    )
    request = known.model_copy(update={
        "build": known.build.model_copy(update={
            "premade_id": "hero.unknown",
        }),
    })

    validation = service.validate_new_character(owner.principal_id, request)
    assert not validation.valid
    assert {
        issue.code.value for issue in validation.issues
    } >= {"unknown_premade_id"}
    with pytest.raises(CharacterDirectoryBuildError):
        service.create_character(owner.principal_id, request)
    assert service.list_characters(owner.principal_id).characters == ()
    repository.close()


def test_public_character_creation_is_schema2_draft_only() -> None:
    """The premade composer is not a second public character-creation API."""

    assert set(CreateCharacterRequest.model_fields) == {
        "display_name",
        "build",
        "loadout",
        "expected_content_set_digest",
        "expected_ruleset_digest",
        "idempotency_key",
    }
    with pytest.raises(ValidationError):
        CreateCharacterRequest.model_validate(
            {
                "display_name": "Legacy",
                "premade_id": "hero.fighter_l5_shield_torch",
            },
        )
